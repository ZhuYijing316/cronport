# 发星指南 / Launch playbook

> 这份文档是给项目作者本人的操作手册，不是仓库文档。
> 目标：在发布后 30 天内拿到 100～300 星，并建立第一批真实用户。

---

## 一、先把预期摆正

| 项目类型 | 典型星标 | cronport 的现实目标 |
| --- | --- | --- |
| 大众工具（JSON 格式化、颜色转换） | 1k～20k | — |
| 窄而深的专业工具 | 100～1,500 | **100～300 是好成绩，500 很好** |
| 资源清单（awesome list） | 500～8,000 | — |

**第一个项目的星标，衡量的是「完成度 + 是否被看见」，不是「用户量」。**
一个 300 星、README 漂亮、CI 全绿、有真实用户反馈的项目，
对面试和接活的加成远大于一个 3000 星但 README 混乱的项目。

所以这套打法的顺序是：**先把东西做到能拿出手 → 再花力气让它被看见。**

---

## 二、发布前检查清单（半天）

一份清单，挨个打勾，别跳。

### 内容

- [ ] `README.md` 首屏有：一句话定位、5 张 badge、demo GIF、3 个命令的输出示例
- [ ] demo GIF 是真跑的（`make demo` 重新生成过）
- [ ] 中文 README 独立成篇（`README.zh-CN.md`），顶部互相链接
- [ ] `docs/dialects.md` 存在且准确
- [ ] `docs/examples.md` 里有至少 5 个真实场景
- [ ] `CHANGELOG.md` 有 `0.1.0` 条目
- [ ] `LICENSE` 已填上你的名字（`scripts/init_user.sh` 会处理）
- [ ] `MAINTENANCE.md` 存在（未来的你会感谢现在的你）

### 技术

- [ ] `make check` 全绿（lint + typecheck + test）
- [ ] CI 在 GitHub 上是绿的
- [ ] `pip install cronport` 在**全新虚拟环境**里能跑通（已验证）
- [ ] `cronport --help` 的输出读起来像一份说明书
- [ ] 至少有一个真实 issue 被修复过（发之前先自己用一周）

### 账号

- [ ] GitHub 个人资料的 bio 写了「作者 of cronport」
- [ ] GitHub 个人资料的 website 指向仓库
- [ ] 头像/用户名没有奇怪的地方（很多人会搜你的名字）
- [ ] 仓库的 topics 填了：`cron`, `crontab`, `scheduler`, `systemd`, `kubernetes`,
      `github-actions`, `devops`, `cli`, `schedule`, `automation`

---

## 三、发布当天

### 1. 建仓库

```console
$ git remote add origin git@github.com:<你的用户名>/cronport.git
$ git push -u origin main
```

### 2. 打第一个 tag

```console
$ git tag -a v0.1.0 -m "v0.1.0"
$ git push origin v0.1.0
```

去 GitHub 的 **Releases → Draft a new release → 选择 v0.1.0**，
把 `CHANGELOG.md` 里 0.1.0 那段复制进去，Publish。

### 3. 发 PyPI（**必做**，不是可选）

**结论：要发。** 理由很直接 —— README 里最关键的那行是
`pipx install cronport`，一行就能装上；没有 PyPI 就只能写
`pip install git+https://github.com/...`，转化率会掉一大截。
而 PyPI 的包名 `cronport` **目前还没被占用**，被人抢走就麻烦了。

流程见 `MAINTENANCE.md` 第 3 节，核心就一条命令：

```console
$ export TWINE_USERNAME=ZhuYijing316
$ export TWINE_PASSWORD=pypi-你的token
$ export GITHUB_TOKEN=github_pat_你的token
$ ./scripts/release.sh 0.1.0
```

（两个 token 的申请链接在 `MAINTENANCE.md` 里，各 2 分钟。）

```console
$ export TWINE_USERNAME=<你的用户名>
$ export TWINE_PASSWORD=pypi-<你的token>
$ ./scripts/release.sh 0.1.0
```

token 在 <https://pypi.org/manage/account/token/> 申请，
Scope 选 `pypi:<你的用户名>:cronport`。

### 4. 写一条「产品公告」

存到你的博客或者一份 Gist，以后每次发版都能改改重用。

---

## 四、去哪发帖（按效果排序）

### 🥇 Hacker News —— 曝光最高，但只接受真话

**规则**：不要标题党，不要「I built」，要写清楚你解决了什么问题。
HN 的读者是工程师，他们对营销文案免疫，对真东西有好感。

**标题备选**（选一个，选完就别改了）：

- `Show HN: cronport – convert cron expressions between scheduler dialects`
- `Show HN: A tool that tells you when your cron expression will actually run`
- `cronport: the day-of-month/day-of-week OR rule nobody warns you about`

**正文模板**（英文）：

```
Hi HN, I built cronport because I moved a crontab to GitHub Actions and it
silently started running 8 hours off.

It does three things:

- explains a cron expression in plain language
- converts it between cron, systemd, Kubernetes, GitHub Actions, AWS
  EventBridge, Quartz and Cloud Scheduler
- lints the traps: the day-of-month/day-of-week OR rule, UTC-only targets,
  steps that drift at the hour boundary, dates that never happen

The interesting bit it encodes is that cron's two day fields are ORed, not
ANDed — so `0 0 13 * 5` fires on the 13th OR every Friday. Quartz ANDs them,
systemd ANDs them too, so a faithful conversion needs two rules there.

Zero dependencies, pure standard library, 168 tests.

    pipx install cronport
    cronport explain "0 9 * * 1-5"

Happy to answer questions about the semantics of any scheduler.
```

**发帖时间**：美东时间的上午 8-10 点（即北京时间晚上 8-10 点）。
周二到周四最好，周末别发。

**注意**：HN 只允许一个 Show HN。发了之后**不要重复发**，
HN 会直接封禁。后续版本就发普通的帖子（标题不带 Show HN）。

### 🥈 Reddit

- `r/devops` —— 最对口
- `r/sysadmin`
- `r/programming` —— 规则严，只发真正有技术含量的
- `r/commandline` —— 对 CLI 工具友好
- `r/kubernetes`

**发帖模板**：

```
Title: cronport – a CLI that converts cron expressions between scheduler
dialects and explains when they'll actually run

I kept running into the same problem: the same schedule means different
things in cron, systemd, Kubernetes, GitHub Actions and AWS EventBridge.

- GitHub Actions: always UTC, no timezone setting
- Kubernetes: UTC unless you set spec.timeZone
- AWS EventBridge: one of the two day fields MUST be ?
- cron ORs day-of-month with day-of-week; Quartz and systemd AND them

So `0 0 13 * 5` fires on the 13th OR every Friday, and `0 9 * * 1-5` moves 8
hours when you paste it into a GitHub Actions workflow.

cronport explains a schedule, converts it between 7 dialects, and lints the
traps. Pure Python standard library, no dependencies.

    pipx install cronport
    cronport explain "0 9 * * 1-5"
    cronport convert "0 9 * * 1-5"
    cronport lint "0 0 13 * 5"

Source: https://github.com/<你的用户名>/cronport
```

**注意**：Reddit 的标题里不要带营销词，别发到 r/promote（那儿只能发自家产品，
但受众不对）。先在评论区认真回答问题再删楼。

### 🥉 中文社区（你的主场）

- **掘金** —— 发技术长文，把 OR 规则讲透，配几张终端截图
- **V2EX** —— 节点选「程序员」或「DevOps」，语气朴实点
- **SegmentFault / 思否** —— 适合教程型文章
- **知乎** —— 回答「cron 表达式怎么看懂」「crontab 怎么改时区」这类问题，
  在答案里提 cronport（不要发广告贴）
- **即刻 / 小红书** —— 技术内容传播弱，但能触达正在找工作的人

**掘金/V2EX 文案模板**（中文）：

```
写了个小工具解决一个每次都要重新查文档的痛点：cron 表达式跨调度器迁移。

最坑的是这几条：
1. cron 的「日」和「星期」同时限定时是「或」不是「且」——
   `0 0 13 * 5` 会在 13 号和每个周五都跑，比你以为的多得多
2. GitHub Actions 固定 UTC 且不能改
3. AWS EventBridge 两个「日」字段必须有一个填 `?`
4. `*/7` 这种步长不整除 60，整点会漂移

工具能做三件事：用人话解释、跨 7 种方言互转、检查这些坑。
零依赖，纯标准库。

    pipx install cronport
    cronport explain "0 9 * * 1-5"
    cronport convert "0 9 * * 1-5"
    cronport lint "0 0 13 * 5"

https://github.com/<你的用户名>/cronport
```

### 4. Twitter / X

发一条，配 GIF 或终端截图。带上 `#cron #devops #kubernetes` 之类。
这个渠道主要是让同行知道，不太会直接带来很多星，但会带来**投稿/邮件**。

### 5. 给 awesome-list 投稿

这是长尾但持续涨星的渠道。目标列表：

- `awesome-cron` / `awesome-scheduler`
- `sindresorhus/awesome`（大列表，对工具质量有要求）
- `awesome-selfhosted`
- 各种 `awesome-devops`、`awesome-k8s`

**投稿模板**（英文）：

```
- [cronport](https://github.com/<你的用户名>/cronport) 🐍 - Explain, convert
  and lint cron expressions across cron, systemd, Kubernetes, GitHub Actions,
  AWS EventBridge, Quartz and Cloud Scheduler. Zero dependencies.
```

被 `sindresorhus/awesome` 收录能一次性带来几百星，但需要：
README 完整、有 demo、有 license、有 CI、不是纯脚本玩具。

---

## 五、发布后 30 天

| 时间 | 做什么 |
| --- | --- |
| 第 1 天 | HN + Reddit + 中文社区，同一天发完 |
| 第 1 周 | 每天回复所有评论和 issue（算法偏爱活跃的仓库） |
| 第 2 周 | 给 3～5 个 awesome-list 投稿 |
| 第 3 周 | 写一篇「cron 的 OR 语义」的技术文章，发到掘金 + HN（Show 过一次了，这次是普通帖） |
| 第 4 周 | 根据 issue 反馈发 0.2.0，并在 release notes 里感谢贡献者 |

### 一个小技巧：制造「可分享的知识点」

纯工具不好传播，**知识点**好传播。

「cron 的 day-of-month 和 day-of-week 是 OR 不是 AND」这个知识点，
本身就能独立成为一篇爆款文章，文章里带上工具链接。

同理：
- 「GitHub Actions 调度为什么总是差 8 小时」
- 「systemd OnCalendar 和 cron 到底差在哪」
- 「为什么 `*/7` 的 cron 不是每 7 分钟」

**这类文章比工具本身涨星快得多**，而且是长尾流量。

---

## 六、别做的事

- ❌ 不要同时在十几个平台发同样的文案（会被当成 spam）
- ❌ 不要买 star（GitHub 会清理，而且新人这么干会掉口碑）
- ❌ 不要发「求点赞」——这是最劝退工程师的行为
- ❌ 不要在 issue 里跟人争论「这是 bug 还是特性」
- ❌ 不要为了星标去提交低质量的 PR 给别的项目

---

## 七、如果你只有 30 分钟

优先级排序：

1. **把 README 首屏做完**（1 小时）—— 决定 80% 的转化
2. **发 Hacker News**（30 分钟）—— 单次曝光最高
3. **发 Reddit r/devops**（15 分钟）
4. **录 demo GIF**（30 分钟，`make demo`）
5. **发 PyPI**（20 分钟）

剩下的都可以慢慢来。

---

## 八、需要我帮忙的时候

把这些东西给我，我直接给你成品：

- 「issue 来了，内容如下：……」→ 我给你修复代码 + 回复文案
- 「帮我写一篇讲 OR 语义的文章」→ 我给你写好中英文两版
- 「帮我写 0.2.0 的 release notes」→ 我给你写好
- 「这个 PR 该不该合」→ 我给你判断依据
