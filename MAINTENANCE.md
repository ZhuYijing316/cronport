# 维护手册 / Maintenance Guide

这份文档写给**一个人**：项目作者本人。它假设你不会写 Python，也假设你
每月只有半小时。

看完这一篇，你应该能独立处理 90% 的情况。

---

## Windows 用户：先看这一节

### 怎么打开终端（不用右键菜单）

右键菜单里的「Open Git Bash here」**你不需要它**。三种打开方式，任选一个：

| 方式 | 怎么做 |
| --- | --- |
| **开始菜单** | 按 Win 键 → 输入 `Git Bash` → 回车 |
| **PowerShell** | 按 Win 键 → 输入 `PowerShell` → 回车（**推荐**，脚本都支持） |
| **Windows Terminal** | Win 键 → 输入 `Terminal` → 回车 |

打开终端后，**先确认 git 装没装**：

```console
PS> git --version
git version 2.5x.x.windows.1
```

看到版本号 = 装好了 ✅ 直接往下做。

如果提示「不是内部或外部命令」，用这一行装（需要管理员权限的终端）：

```console
PS> winget install --id Git.Git -e --source winget
```

装完**关掉终端重新开一个**，再试 `git --version`。

### 关于右键菜单那条

如果你还是想让它出现在右键菜单里（Win11 默认把它折叠了）：

- **按住 `Shift` 再右键** —— 直接出完整菜单，最省事
- 或者右键 → 点最下面的「**显示更多选项**」
- 如果那里也没有：开始菜单 → 找到 `Git Bash` → 右键 → **打开文件所在位置** → 在那个文件夹里
  空白处右键，看有没有「在此处打开 Git Bash」
- 还是没有的话，说明安装时没勾「Windows Explorer integration」，可以重新运行安装包选
  **Repair** 修复

### 你的脚本有两个版本

| 系统 | 推送 | 发版 |
| --- | --- | --- |
| macOS / Linux | `./scripts/first_publish.sh` | `./scripts/release.sh 0.1.0` |
| **Windows** | `powershell -ExecutionPolicy Bypass -File .\scripts\first_publish.ps1` | `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 0.1.0` |

Windows 版还多做了一件事：**它用你的 token 直接把仓库在 GitHub 上建出来**，
所以你连「新建空仓库」那一步都不用手动做。

Windows 版第一次运行可能会被 Windows 的安全策略拦住（红色横幅），
按 **Shift + 右键 → 使用 PowerShell 运行** 就不需要改任何设置。

---

## 0. 你需要记住的三件事

1. **写代码不是你的活。** 有人提 issue → 把内容复制粘贴给我 → 我给你修复
   代码和回复文案 → 你贴回去。
2. **发版不是复杂操作。** 一条命令。
3. **不做也没关系。** 任何时候你不想管了，可以把仓库归档。没人指望你的
   第一个项目维护十年。

---

## 1. 每月十分钟例行

打开仓库，看一眼 Issues 列表：

| 你看到什么 | 你该做什么 |
| --- | --- |
| 没人提新 issue | 什么都不用做 ✅ |
| 有人问「怎么用」 | 从 [回复模板](#4-回复模板) 里抄一段，改两三个字，回复 |
| 有人报 bug，附了表达式 | 复制给我，我给你修复 |
| 有人提新功能 | 复制给我，我判断值不值得做 |
| 有人提 PR | CI 会自动跑测试。绿了就点 Merge，红了复制给我 |

**判断标准很简单**：需要「写代码」或「做技术判断」的，都交给我；
需要「打字回复」的，你自己来。

---

## 2. 收到一个 issue 之后

### 步骤 1：先看 linter 是不是已经说过了

大多数「不对劲」的调度，`cronport lint` 已经能指出问题。让提问者先跑：

```console
$ cronport lint "他们的表达式"
```

如果 lint 已经指出了问题，你直接回复：

> 你的表达式确实有个已知问题，lint 已经指出来了：
> ```
> $ cronport lint "0 0 13 * 5"
> ⚠ dom-dow-or
>     「日」和「星期」同时被限定，触发条件是满足任意一个（OR）
> ```
> 修法是把它拆成两条规则，或者改用 Quartz。

### 步骤 2：需要我的时候

把 issue 的**完整内容**复制粘贴给我，包括：

- issue 标题
- issue 正文
- 对方的系统信息（如果模板里有填）

我会还给你：

- 一段可以直接发的回复
- 如果是 bug：修复好的代码
- 如果需要发版：CHANGELOG 条目

### 步骤 3：回复并关闭

把回复贴回 issue，勾选 Close。

---

## 3. 发一个新版本

什么时候发版：

- 修了一个 bug → 发
- 加了一个新方言或新规则 → 发
- 只改了文档 → 不用发

### 步骤 1：改版本号

改 `pyproject.toml` 里的 `version = "0.1.0"` → `"0.1.1"`。

### 步骤 2：写 CHANGELOG

在 `CHANGELOG.md` 最上面加一段：

```markdown
## [0.1.1] - 2026-11-10

### Fixed

- 修复了 ... 的问题
```

### 步骤 3：提交

```console
$ git add -A
$ git commit -m "Release 0.1.1"
$ git push
```

### 步骤 4：一条命令发布

**macOS / Linux：**

```console
$ export TWINE_USERNAME=ZhuYijing316
$ export TWINE_PASSWORD=pypi-你的token
$ export GITHUB_TOKEN=github_pat_你的token
$ ./scripts/release.sh 0.1.1
```

**Windows（PowerShell）：**

```console
PS> $env:TWINE_USERNAME = "ZhuYijing316"
PS> $env:TWINE_PASSWORD = "pypi-你的token"
PS> $env:GITHUB_TOKEN = "github_pat_你的token"
PS> powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 0.1.1
```

这条命令会自动：跑测试 → 打包 → 检查 → 上传 PyPI → 打 git tag 并推送 →
创建 GitHub release（release 说明会自动从 CHANGELOG 里抽取）。

**如果不想发 GitHub release**，把 `GITHUB_TOKEN` 留空即可，脚本会跳过那一步，
你之后在网页上手动创建也来得及。

**脚本会拦住你**的情况：版本号和 `pyproject.toml` 对不上、CHANGELOG 里没有
对应段落、有没提交的改动、tag 已经存在、测试没通过。它不会替你做错决定。

**两个 token 怎么拿**：

- **PyPI**：<https://pypi.org/manage/account/token/>，Name 填 `cronport`，
  Scope 选 `pypi:ZhuYijing316:cronport`，点 Create token 后复制生成的
  `pypi-...` 字符串（只显示一次）
- **GitHub**：<https://github.com/settings/tokens>，新建 personal access token，
  勾选 `repo` 权限，复制 `github_pat_...`

---

## 4. 回复模板

存在 `docs/reply-templates.md`，直接复制改几个字就能用。常见场景：

- 「怎么把 cron 转成 K8s」
- 「怎么让它按我本地时间跑」
- 「这个表达式什么意思」
- 「报错了」（Windows 路径问题）
- 「能加一个 XX 方言吗」

---

## 5. 常见情况速查

### 有人问「要不要用 Docker / 有没有二进制版」

> 目前只发布 pip 包，但它是纯标准库没有任何依赖，安装很快：
> `pipx install cronport`。如果你更希望有独立二进制文件，可以开个 issue 记录一下。

### 有人说「在我的 Windows 上报错」

Windows 上如果报 `ModuleNotFoundError`，多半是用了 `python cronport.py` 而不是
装包。让他跑：

```console
> pipx install cronport
> cronport --version
```

### 有人提了一个新方言

先复制给我。我需要知道：

- 这个调度器的语法长什么样（官方文档链接最好）
- **它的「日」字段是「且」还是「或」**（这是最容易出错的地方）
- **它的时区怎么处理**
- 有没有秒字段

拿到这些我能很快加上去。

### 有人抱怨缺少功能

先复制给我。这类回复最影响星标和口碑，值得认真对待。

---

## 6. 什么时候该收手

如果连续两个月没人提 issue、也没有新的 star，那是正常现象，不代表项目失败。

开源项目大部分时间都是静默的。你不需要为「这个月没动静」有任何心理负担。

如果某天你实在不想维护了：

1. 在 README 顶部加一行：`*This project is looking for a new maintainer.*`
2. 或者在仓库设置里点 **Archive**（归档）

归档不会影响它作为你作品的一部分的价值。一个完成度高的项目，哪怕归档了，
也远比一个半成品有说服力。

---

## 7. 一年一次的检查

每年花五分钟看一眼：

- GitHub 有没有 Security advisory 需要处理
- 依赖有没有过期（cronport 本身零依赖，主要是看 CI 里的 action 版本）
- README 里的安装命令还能不能跑通

```console
$ pip install cronport && cronport --version
```

---

## 8. 常用命令速查

| 目的 | 命令 |
| --- | --- |
| 跑全部测试 | `make test` |
| 只用标准库跑测试 | `make test-standalone` |
| 代码风格检查 | `make lint` |
| 类型检查 | `make typecheck` |
| 打包 | `make build` |
| 发布 | `./scripts/release.sh <版本号>` |
| 重新生成演示动图 | `make demo` |
