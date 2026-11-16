# ============================================================
# 韩语情境闯关 · GitHub Pages 部署说明
# ============================================================
#
# 【方案选择】本仓库提供两种发布布局，按需选一种：
#
#   方案 A（推荐）：仓库根目录直接放 index.html
#     · GitHub Pages 设为「Deploy from a branch」→ 选择 main 分支 → 目录选 / (root)
#     · 访问地址：https://<用户名>.github.io/<仓库名>/
#     · 优点：URL 最短；缺点：文档和工具也一起发布出去了
#
#   方案 B：把游戏放 docs/ 目录
#     · GitHub Pages 设为「Deploy from a branch」→ 选择 main 分支 → 目录选 /docs
#     · 访问地址：https://<用户名>.github.io/<仓库名>/docs/
#     · 优点：只发布游戏本体，仓库根目录放 README 和工具，很干净
#
# 【关键设置】务必在仓库 Settings → Pages 里：
#     1. Source 选 "Deploy from a branch"
#     2. Branch 选 main（或你实际用的分支名）
#     3. 目录选 / (root) 或 /docs（对应上面方案）
#     4. 不要勾选 "Deploy from a branch" 之外的 GitHub Actions（除非你熟悉它）
#
# 【重要】本项目已包含 .nojekyll 文件，会跳过 Jekyll 构建。
#     这样能避免 Jekyll 处理中文文件名、忽略下划线目录等意外行为。
#
# ============================================================

## 一、本地验证（发布前必做）

```bash
# 1) 项目自检（7 项）
python tools/self_check.py

# 2) GitHub Pages 部署专项验证（模拟子路径 + 静态检查）
python tools/verify_pages.py
```

两个都全绿再推送。`verify_pages.py` 会自动构造模拟目录、挑空闲端口起服务器，
用 `http://localhost:<端口>/<仓库名>/index.html` 这种子路径 URL 完整走一遍游戏——
这正是 GitHub Pages 项目站点的真实访问形态。

## 二、模拟 GitHub Pages 的子路径环境（重要）

GitHub Pages 项目站点部署在子路径 `https://<用户名>.github.io/<仓库名>/`，
比根目录多一层。本项目的资源引用全部使用相对路径，已实测在子路径下正常工作：

```bash
# 构造模拟目录
mkdir -p _pagesim/english-scene-quest
cp -r index.html data assets _pagesim/english-scene-quest/

# 起服务器
python -m http.server 8790 --directory _pagesim

# 浏览器打开（注意子路径）
# http://localhost:8790/english-scene-quest/index.html
```

验证要点：10 关全部可进入、场景图与 NPC 正常加载、完整通关到 100%、无 404。

## 三、首次推送步骤

```bash
# 1. 初始化仓库（在项目根目录）
git init
git branch -M main

# 2. 添加文件
git add -A

# 3. 提交
git commit -m "feat: 韩语情境闯关 · 86 题 · 韩语台词 · 敬语考点 · 像素风"

# 4. 关联远程仓库（替换成你的实际地址）
git remote add origin https://github.com/<用户名>/<仓库名>.git

# 5. 推送
git push -u origin main
```

> `.gitignore` 已配好，`.workbuddy/`、`*.genie`、`__pycache__/` 等本地文件不会被提交。

## 四、开启 Pages

仓库页面 → **Settings** → 左侧 **Pages** → Build and deployment → Source 选 **Deploy from a branch** → Branch 选 **main** → 目录按方案选 **/ (root)** 或 **/docs** → Save。

等待 1–3 分钟构建完成，地址栏会显示你的站点地址。

## 五、常见问题

**Q: 页面空白 / 样式全丢？**
A: 检查 Settings → Pages 的目录选对没有（选 /docs 时文件必须在 docs/ 里）。
   本项目零外部 CSS/JS 依赖，若样式全丢说明 index.html 没被正确发布。

**Q: 场景图 404？**
A: 确认 assets/ 目录已提交。`git ls-files assets | head` 可以看是否入库。

**Q: 修改后没生效？**
A: GitHub Pages 有缓存，强制刷新（Ctrl+Shift+R）。也可在 Actions 页签取消勾选
   "Disable Jekyll" 之外的选项，或直接看 commit 状态页确认构建成功。

**Q: 中文文件名会不会有问题？**
A: 本项目已加 `.nojekyll` 跳过 Jekyll 处理，中文 md 文件名仅影响文档链接，
   不影响游戏运行（游戏资源路径全是英文）。

**Q: AI 教练点评功能能用吗？**
A: 不能。该功能依赖 WorkBuddy 云服务（需要 `window.CLOUD_CONFIG`），
   GitHub Pages 是纯静态环境。代码里已做好降级——云服务不可用时自动切到本地点评，
   游戏功能完全不受影响。

## 六、后续更新

改完代码后：

```bash
git add -A
git commit -m "update: <说明>"
git push
```

Pages 会自动重新构建（1–3 分钟）。
