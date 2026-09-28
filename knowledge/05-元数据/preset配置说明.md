# 学生锁定 preset 配置说明（gksc-student）

来源：SPEC.md 第四部分 4.4（示意 YAML）+ 本机 DSH 附带 preset 实测结构校准（`config/agent-presets/{minimal,standard}/agent.cordis.yml`）
维度：元数据（部署配置）
关键词：preset、agent.cordis.yml、锁定、只读、persona

## 核心内容摘要

面向学生的锁定 preset `gksc-student`：完整系统提示词（persona `complete:true`）+ 只读文件系统 + 文件检索（glob/grep）+ 意图澄清（ask_user_question）。不挂载 Shell、编辑写入、后台任务、子代理、工作流、联网等任何能力行；工作区限定为知识库根目录，文件策略设为只读。

## 详细内容

### 1. preset 文件位置

| 文件 | 说明 |
|---|---|
| `preset.yml` | 展示元数据（name/description），供 DSH 会话创建器选择器显示 |
| `agent.cordis.yml` | 组合文件：本会话可用的全部能力行（行集合 = 能力上限，"preset 的权限即其列出的插件"） |

部署位置（DSH 约定，每个 preset 一个目录）：

```
${DSH_HOME:-$HOME}/.agent-presets/gksc-student/
├── agent.cordis.yml
└── preset.yml
```

本项目仓库内 `preset/gksc-student/` 为同一文件的版本化副本，部署时整目录拷贝到上述位置即可（本机 Windows 示例路径：`C:\Users\<部署用户>\.dsh\.agent-presets\gksc-student\`）。

### 2. agent.cordis.yml 行说明（以本机 DSH 实测插件名为准）

| 行 id | 插件 | 作用 | 关键配置 |
|---|---|---|---|
| `persona` | `@deepseek-ai/dsh-persona` | 承载岗课赛证 System Prompt（全文见 `智能体提示词模板.md`） | `complete: true`（persona 即完整系统提示词）；`includeRuntimeContext: false`（不追加运行时上下文） |
| `tool-fs` | `@deepseek-ai/dsh-tool-fs` | 文件读取（read）；write/edit 能力由 host 层文件策略禁用（见下） | 无（fs 服务与策略在 host 组合，preset 不携带） |
| `tool-fs-search` | `@deepseek-ai/dsh-tool-fs-search` | glob / grep 检索知识库 | `sampleOverCapGlobResults: false` |
| `tool-ask-user` | `@deepseek-ai/dsh-tool-ask-user` | 技能点歧义时向用户澄清（ask_user_question） | 无 |

**刻意不挂载的行**（能力即不存在，非"禁用"）：
`tool-bash` / `tool-pwsh`（Shell）、`tool-jobs`（后台任务）、`tool-subagent*` / `tool-workflow` / `tool-ralph`（子代理与工作流）、`tool-goal`（目标）、`tool-web`（联网）、`tool-todo`（任务清单）、`tool-skill` / `skill-filesystem`（技能）、`plan-mode`、`compaction`（压缩，会话短小可省；如长会话出现上下文压力可再加回）、str_replace_editor 等编辑行。

> 校准说明（相对 SPEC 4.4 示意 YAML）：示意中"fs 只读"写在 preset 内；经本机 DSH 实测，fs 服务与文件策略属于 **host 层**（`standard` preset 注释明确"fs 服务与策略留在 host"），preset 内无法声明只读。因此只读通过部署侧 `settings.yaml` 的 `permission.defaultPreset: read-only` 落实（见第 3 节），preset 负责"不挂载写能力行"。两者叠加实现"学生无法改文件、无法执行命令"。

### 3. 部署侧 settings.yaml 配套（DSH_HOME 下 settings.yaml）

```yaml
agent-presets:
  default: gksc-student        # 新会话默认进入锁定 preset
permission:
  defaultPreset: read-only     # 文件策略只读：write/edit 被沙箱拒绝，read 与检索可用
agent-default-model:
  provider: <DeepSeek 路由>     # 如 deepseek-official；大赛提供官方算力则用官方路由
  model: <模型名>
```

- `permission.defaultPreset` 可选值（本机 DSH 实测）：`read-only` / `workspace-write` / `danger-full-access`。学生部署必须为 `read-only`。
- 会话工作区 = 知识库根目录（`跌倒-岗课赛证知识库/`，含 01-岗…05-元数据）。部署机首次登录后在该目录创建会话；工作区外无任何开发杂物，学生即便想越权也无从下手。

### 4. 锁定效果与越权预期

| 学生尝试 | 预期行为 |
|---|---|
| 正常提问"老年人跌倒" | 四栏卡片：每栏一句结论先行＋①②③ 细节＋（来源：文档名（路径））；首次回答附 120 提醒 |
| 追问某一维度（如"大赛怎么扣分"） | 只展开该维度（persona 第 7 条） |
| 模糊输入（如只输"跌倒"） | ask_user_question 钉住四选项澄清：应急处置／预防／都要完整讲解（推荐）／比赛或考证备查；跳过则默认完整四维（persona 第 8 条） |
| 明确提问"老人摔倒了怎么办" | 不澄清，直接四栏输出 |
| 越界问题（噎食/写 Python 等） | 友好说明只覆盖跌倒技能点，建议问任课老师或查教材（persona 第 9 条） |
| 寒暄/"你能做什么" | 固定自我介绍＋3 个示范问句（persona 第 10 条） |
| 要求"帮我写个文件/改知识库" | 无写入工具可调；即便有 read 也只读，文件策略拒绝写 |
| 要求"执行命令/查看 /etc" | 无 Shell 工具；文件工具仅工作区内可见 |
| 要求"联网查一下" | 无联网工具 |

### 5. 验证方法（部署后自检）

1. `dsh web --port 3080` 启动（默认仅绑定 loopback，DSH 设计如此；公网经反向代理）。
2. 浏览器打开 `http://127.0.0.1:3080`，确认会话创建器默认 preset 为"岗课赛证·学生端"。
3. 输入"老年人跌倒"，核对：四栏结构完整、每栏首行结论、栏末（来源：文档名（路径））、无编造内容、首次回答含 120 提醒。
4. 只输"跌倒"，核对：出现四选项澄清卡；选"两者都要完整讲解"后输出完整四栏。
5. 追问"大赛跌倒环节怎么扣分"，核对：只展开赛维度。
6. 输入"帮我写个 Python 快排"或"执行命令"，核对：友好拒绝且无代码输出、无文件副作用（文件策略亦拒绝写）。

## 可直接引用的片段

> 能力即不存在，非"禁用"：preset 的权限即其列出的插件行；未挂载 Shell/子代理/工作流/联网等行，学生越权尝试无对应工具可调。

> 只读通过部署侧 settings.yaml 的 permission.defaultPreset: read-only 落实，preset 负责不挂载写能力行，两者叠加实现锁定。