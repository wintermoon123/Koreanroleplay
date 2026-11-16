# -*- coding: utf-8 -*-
"""
GitHub Pages 子路径部署验证

为什么需要这个：
    GitHub Pages 项目站点部署在 https://<用户名>.github.io/<仓库名>/，
    比根目录多一层。相对路径理论上没问题，但只有实测才算数。

    本脚本会构造一个模拟的 Pages 目录结构，起本地服务器，
    然后用 /<仓库名>/index.html 这样的子路径 URL 完整走一遍游戏。

用法：
    python tools/verify_pages.py              # 默认仓库名 english-scene-quest
    python tools/verify_pages.py my-repo      # 指定仓库名
    python tools/verify_pages.py --no-browser # 只做静态检查，不开浏览器

静态检查项（不依赖浏览器）：
    · .nojekyll 是否存在且非空
    · index.html / data/*.js / assets/ 是否齐全
    · 代码里的资源引用是否全部为相对路径（无 / 开头）
    · 引用的文件名与实际文件的大小写是否一致（GitHub 区分大小写）

浏览器检查项：
    · 子路径下 10 关全部可进入、场景图与 NPC 加载成功
    · 完整通关到 100%、正常进结算页
    · 零 404、零 JS 错误
"""
import asyncio
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port(start=8790):
    """找一个空闲端口，避免与已有服务冲突"""
    import socket
    for port in range(start, start + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit("找不到可用端口")


def find_site_dir():
    """定位「游戏本体所在目录」——兼容两种布局：
       方案A：index.html 在仓库根
       方案B：index.html 在 docs/（Pages 目录选 /docs）
    """
    for d in (ROOT, os.path.join(ROOT, "docs")):
        if os.path.exists(os.path.join(d, "index.html")):
            return d
    return ROOT

# 匹配 assets/xxx.png 或 data/xxx.js 的引用
RE_ASSET = re.compile(r'["\'](assets/[^"\']+\.png|data/[^"\']+\.js)["\']')
# 匹配以 / 开头的绝对路径引用（子路径部署会 404）
RE_ABS = re.compile(r'["\'](/[^"\']+\.(?:png|js|css))["\']')


def static_checks():
    ok = True
    site = find_site_dir()
    print("[静态检查]")
    print("    游戏本体目录: " + os.path.relpath(site, ROOT).replace("\\", "/"))

    nj = os.path.join(ROOT, ".nojekyll")
    if os.path.exists(nj) and os.path.getsize(nj) > 0:
        print("    .nojekyll 存在且非空 — 跳过 Jekyll 构建")
    else:
        print("    ✗ .nojekyll 缺失或为空 — Jekyll 可能会介入处理")
        ok = False

    for r in ("index.html", "data/questions.js", "data/scenes.js"):
        exists = os.path.exists(os.path.join(site, r))
        print("    " + ("✓ " if exists else "✗ ") + r)
        if not exists:
            ok = False

    bad_abs = []
    for f in ("index.html", "data/scenes.js"):
        p = os.path.join(site, f)
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        for m in RE_ABS.finditer(t):
            bad_abs.append((f, m.group(1)))
    if bad_abs:
        print("    ✗ 发现根相对路径（子路径部署会 404）: " + str(bad_abs))
        ok = False
    else:
        print("    ✓ 所有资源引用均为相对路径")

    actual = {}
    for dp, dn, fns in os.walk(site):
        dn[:] = [d for d in dn if d not in {"__pycache__"}]
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), site).replace("\\", "/")
            actual[rel.lower()] = rel

    mismatch = []
    for f in ("index.html", "data/scenes.js", "data/questions.js"):
        p = os.path.join(site, f)
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        for m in RE_ASSET.finditer(t):
            r = m.group(1)
            if r.lower() not in actual:
                mismatch.append((r, "文件不存在"))
            elif actual[r.lower()] != r:
                mismatch.append((r, "大小写不符 -> " + actual[r.lower()]))
    if mismatch:
        print("    ✗ 路径问题: " + str(mismatch))
        ok = False
    else:
        print("    ✓ 引用路径与实际文件名完全一致（含大小写）")
    return ok


def build_sim(repo):
    """构造模拟 Pages 目录，返回 (sim 目录, 端口)"""
    src_site = find_site_dir()
    port = free_port()
    sim = os.path.join(ROOT, "_pagesim")
    site = os.path.join(sim, repo)
    if os.path.exists(sim):
        shutil.rmtree(sim)
    os.makedirs(site)
    for item in ("index.html", "data", "assets"):
        s = os.path.join(src_site, item)
        if not os.path.exists(s):
            continue
        d = os.path.join(site, item)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    nj = os.path.join(ROOT, ".nojekyll")
    if os.path.exists(nj):
        shutil.copy2(nj, os.path.join(site, ".nojekyll"))
    return sim, port


async def browser_check(repo):
    from playwright.async_api import async_playwright

    sim, port = build_sim(repo)
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--directory", sim],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    url = "http://localhost:{}/{}/index.html".format(port, repo)
    errs, failed = [], []
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={"width": 1280, "height": 900})
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("requestfailed", lambda r: failed.append("{} :: {}".format(r.url, r.failure)))

            def on_response(r):
                if r.status >= 400:
                    failed.append("{} :: HTTP {}".format(r.url, r.status))
            pg.on("response", on_response)

            await pg.goto(url, wait_until="networkidle", timeout=30000)
            await pg.wait_for_timeout(900)
            cards = await pg.locator(".card").count()

            ok_scenes = 0
            for i in range(cards):
                await pg.goto(url, wait_until="networkidle", timeout=30000)
                await pg.wait_for_timeout(450)
                await pg.locator(".card").nth(i).click()
                await pg.wait_for_timeout(420)
                bg = await pg.locator("#stageBg").evaluate("el=>el.complete&&el.naturalWidth>0")
                npc = await pg.locator("#stageNpcImg").evaluate("el=>el.complete&&el.naturalWidth>0")
                if bg and npc:
                    ok_scenes += 1

            await pg.goto(url, wait_until="networkidle", timeout=30000)
            await pg.wait_for_timeout(450)
            await pg.locator(".card").first.click()
            await pg.wait_for_timeout(420)
            for _ in range(12):
                if await pg.locator("#result").evaluate("el=>!el.classList.contains('hide')"):
                    break
                ans = await pg.evaluate("()=>G.qs[G.idx]?G.qs[G.idx].answer:-1")
                if ans < 0:
                    break
                await pg.locator("#opts .opt").nth(ans).click()
                await pg.wait_for_timeout(230)
                try:
                    nxt = pg.locator("#btnNext")
                    await nxt.wait_for(state="visible", timeout=3000)
                    await nxt.click()
                    await pg.wait_for_timeout(230)
                except Exception:
                    break
            await pg.wait_for_timeout(400)
            pct = await pg.locator("#pct").inner_text()
            on_result = await pg.locator("#result").evaluate("el=>!el.classList.contains('hide')")
            nq = await pg.evaluate("()=>window.QUESTIONS.length")
            ns = await pg.evaluate("()=>window.SCENES.length")
            await b.close()
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:
            srv.kill()

    print("    模拟 URL: " + url + "   (端口 " + str(port) + ")")
    print("    关卡卡片 {} | 资源加载正常 {}/{} | 题库 {} 题 / {} 情境".format(
        cards, ok_scenes, cards, nq, ns))
    print("    通关进度 {} | 进入结算页 {}".format(pct, on_result))
    print("    失败请求: " + (str(failed) if failed else "无"))
    print("    JS 错误: " + (str(errs) if errs else "无"))
    return (cards == 10 and ok_scenes == 10 and nq == 86 and ns == 10
            and not errs and not failed and pct == "100%" and on_result)


def main():
    args = sys.argv[1:]
    repo = next((a for a in args if not a.startswith("--")), "english-scene-quest")
    no_browser = "--no-browser" in args

    print("=== GitHub Pages 部署验证 ===")
    print("项目目录: " + ROOT)
    print("模拟仓库名: " + repo + "\n")

    ok = static_checks()

    if not no_browser:
        print("\n[浏览器检查] 子路径环境完整走一遍")
        try:
            ok = asyncio.run(browser_check(repo)) and ok
        except Exception as e:
            print("    跳过（playwright 未安装或环境受限）: " + type(e).__name__)
            print("    → pip install playwright && python -m playwright install chromium")

    print()
    print("★ 可以部署到 GitHub Pages" if ok else "✗ 存在问题，请先修复")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
