# 防跌学堂 · 安全扫描与修复报告

- **日期**：2026-09-29
- **对象**：防跌学堂（FallLearn）公网部署实例 `http://121.199.161.117:8010`（阿里云 ECS · Ubuntu 24.04 · FastAPI + SQLite + Vue SPA）
- **范围**：服务器访问层、应用后端、前端依赖、静态代码、动态行为（DAST）
- **方法**：开源扫描工具（Bandit / OSV / Nuclei / sshd 配置审计）+ 人工代码审查，发现 → 修复 → 复扫 → 回归验收闭环

---

## 一、工具链

| 工具 | 版本 | 用途 |
|---|---|---|
| Bandit | 1.9.4 | Python 静态安全分析（SQL 注入/弱哈希/异常处理等） |
| OSV.dev API | — | 依赖漏洞库查询（PyPI 8 包 + npm 8 包；pip-audit 因网络限制改用 OSV） |
| Nuclei | 3.3.7 | 动态漏洞扫描（DAST，9000+ 模板，medium/high/critical 档） |
| sshd 配置审计 | sshd -T 有效配置 + 人工 | 服务器 SSH 暴露面 |
| 人工审查 | — | 鉴权/越权/路径穿越/CORS/上传/信息泄露 逐项走查 |

## 二、发现与修复

### A. 服务器访问层（高危 → 已修复）

| # | 发现 | 风险 | 修复 |
|---|---|---|---|
| A1 | 22 端口对全网开放 + 弱密码 | 撞库 → 整机失守（含 AI 密钥、试用额度） | 密码换 24 位随机串；sshd **仅密钥登录**（`PasswordAuthentication no`） |
| A2 | `PermitRootLogin yes` | root 直接暴露 | `prohibit-password`（密钥允许、密码禁止） |
| A3 | X11 转发 / TCP 转发开启、MaxAuthTries 6 | 不必要的攻击面 | 全部关闭/收敛为 3 |

### B. 应用层（高危/中危 → 已修复）

| # | 发现 | 风险 | 修复 |
|---|---|---|---|
| B1 | JWT 签名密钥硬编码在公开源码（GitHub 仓库可见） | 任何人可伪造教师 token 绕过登录 | 密钥外置：环境变量优先，缺省自动生成随机密钥持久化（`backend/jwt_secret`，0600，gitignore 排除） |
| B2 | 登录接口无失败限制 | 暴力枚举账号 | 同 IP 10 分钟 5 次失败 → 锁定 10 分钟（429） |
| B3 | AI 提问无每日上限，演示账号公开 | AI 资源被刷 + 演示数据污染 | 每生 30 问/天，超限 429 友好提示 |
| B4 | CORS `allow_origins=["*"]` | 跨域探测面 | 收敛为本平台来源白名单（生产同源 + 本地开发端口） |
| B5 | 缺安全响应头 | MIME 嗅探/点击劫持/引用泄露 | 增加 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer` |
| B6 | 静态文件/上传目录用 `startswith` 做包含判定 | 前缀兄弟目录误判（`uploads2` 类） | 改 `os.path.commonpath` 严格包含判定（2 处） |
| B7 | 图片上传仅校验扩展名 | 伪装扩展名上传非图片内容 | 增加文件头魔数校验（PNG/JPEG/WebP/GIF 四格式） |
| B8 | bcrypt cost=4（6 处） | 密码哈希强度弱（约 16ms/次） | 全部升至 cost=10（存量哈希兼容，改密自动升级） |
| B9 | 公告删除接口漏 `commit()` | 删除静默回滚（返回成功但数据未删） | 补 commit；并新增 `tools/audit_commit.py` 写语句审计工具防同类 |

### C. 依赖漏洞（OSV 数据库）

| 包 | 原版本 | 漏洞 | 处置 |
|---|---|---|---|
| python-multipart | 0.0.20 | 7 条（2 HIGH：二次方复杂度查询串 DoS、无界 multipart 头 DoS；1 HIGH 任意文件写[非默认配置]；3 LOW） | **升级 0.0.32** |
| fastapi / uvicorn / pydantic / PyJWT / bcrypt / httpx / websockets | 见 requirements | 无 | 保持并**锁定版本** |
| 前端 vue / vue-router / vite / esbuild / rollup / postcss 等 8 包 | 见 package.json | 无 | 保持 |

同时 `requirements.txt` 由无版本约束改为**全量锁定**（可复现构建、服务器/本地一致）。

### D. 静态扫描（Bandit）

- 初扫 30 条：0 HIGH，22 MEDIUM（全部为 B608 字符串拼接 SQL 告警），8 LOW。
- **22 条 B608 逐条人工复核**：均为「`?` 占位符拼接」或「表名来自硬编码白名单常量」，参数全部参数化绑定，**无真实注入面**，加 `# nosec B608` 注释说明并留档。
- 8 条 LOW（try-except-pass/continue）为 DSH 本地中继通道的**有意容错降级**设计，接受风险。
- **复扫结果：0 B608，仅余 8 LOW（已说明）**。

### E. 动态扫描（Nuclei DAST）

- **参数**：nuclei 3.3.7，6559 模板（medium/high/critical 档），限速 15 req/s，并发 25，超时 10s
- **结果**：**0 命中**（无中/高/危漏洞告警）；11492 个探测请求，102 个请求级错误（404/405/超时——目标为单端口 SPA，非 Web 服务器特征路径，属正常未命中）
- 扫描覆盖了 SQL 注入、XSS、路径穿越、信息泄露、敏感文件暴露、CORS 误配置、SSRF 等类别的公开模板
- 扫描期间登录节流按设计生效（探测的暴力登录尝试被 429 拦截）；扫描后数据库已恢复演示初始态
- 局限性说明：模板扫描为特征匹配，不替代人工审查（F 节）；未做认证态后的越权遍历（已按 F 节人工完成）

### F. 人工审查结论（无漏洞项，留档）

- 前端 **零 `v-html`**：所有用户/AI 内容走 Vue 插值（自动转义），无 DOM XSS 面。
- 上传端点：教师鉴权 + 4MB 上限 + 扩展名白名单 + **服务端重命名**（不用用户文件名）+ 魔数校验。
- `/api/admin`、`/api/manage` 全部端点 `require_teacher`；`/api/content`、`/api/meta` 仅只读公开数据（轮播/公告/簇名）。
- AI 密钥只存服务端数据库，管理端 API 返回打码视图，前端构建产物全文检索 `sk-` 零命中。
- 错误处理：422→400 中文可读错误、无堆栈外泄；500 无响应体。

## 三、接受的风险（说明）

| 风险 | 说明 |
|---|---|
| HTTP 明文（无 TLS） | 比赛周期内无域名/ICP 备案条件；登录已加节流、数据面已加限次，密码为演示账号。赛后上域名为 P0 改进项 |
| JWT 30 天有效期 | 演示场景可接受；无 refresh 需求，到期重登 |
| SQLite 单文件 | 比赛规模（4 演示账号 + 1363 题）足够；WAL 模式已开 |
| Bandit 8 LOW | 有意的本地中继容错降级，注释说明 |

## 四、复验结果

- Bandit 复扫：0 B608 / 0 MEDIUM / 0 HIGH
- 全套功能回归（安全修复后）：api 21/21 + 下钻 11 + E2E 28/28 + smoke ALL PASS + AI 直连 9/9 —— **全绿**
- 服务器演示数据恢复初始态（1 公告 / 2 演示考卷 / AI 配置就绪）

## 五、持续安全机制

1. 依赖全锁版本，升级走 OSV 复查；
2. 扫描工具链可一键重跑（本报告工具均可复现）；
3. DeepSeek 消费预警（控制台配置）——AI 资源兜底告警；
4. 服务器到期（2026-12-18）前评估释放/转包月，避免闲置风险；
5. 代码修改走 Git 提交（含安全修复记录），仓库即审计轨迹。

---

# 第二轮加固（P1.1，2026-09-29 晚）

- **范围**：应用后端（13 个模块全量代码走查）+ 前端（20 个 SFC）+ 依赖树 + 静态/动态扫描
- **方法**：Bandit / pip-audit(OSV) / OSV npm / 人工按 OWASP Top 10 逐项走查 / 自动化安全验收脚本
- **新增验收脚本**：`tools/security_check.py`（26 项，可一键复跑）、`tools/ui_check.py`（界面与转义验收）

## A. 高危修复（学生端可实际利用 → 已修复）

| # | 发现 | 风险 | 修复 |
|---|---|---|---|
| A1 | 错题复习可无限刷分/刷学时：`/api/wrong/review` 对已掌握错题仍接受重答，每次答对 +10 积分 +1 分钟学时，无幂等 | 单账号脚本可刷出任意积分/学时，污染排行榜与教师端统计 | 仅接受 `status='active'` 记录（已掌握 → 404）；**只有「到期」复习才计分/计掌握度/计学时**（未到期仅练习，明确提示不计分）；复习学时每日封顶 30 分钟 |
| A2 | 交卷/开卷竞态：`/quiz/submit` 为「先查状态后写」，无事务与唯一约束；并发提交可重复加分、写入重复作答行 | 并发重复交卷 → 积分/掌握度翻倍、班级统计失真 | 交卷改为**条件更新幂等闸门**（`UPDATE … WHERE status='open'`，rowcount=0 即拒绝）；数据库新增 `UNIQUE(attempt_id,question_id)` 与部分唯一索引 `UNIQUE(student_id,exam_id) WHERE status='open'`（迁移时自动去重历史脏数据）；开卷冲突捕获 `IntegrityError` 转为断点续考 |
| A3 | 全站无请求体上限 + `question` 无长度限制（可 POST 200MB 文本打满单进程内存） | 拒绝服务（演示期被单请求打挂） | 全局 `Content-Length > 6MB → 413` 中间件；`AskIn.question` 限 2–1000 字；作答字典限 200 键/值 ≤20 字；KB 检索词限 100 字/8 词；上传改**分块读 + 累计判长**（不再一次性读入内存） |

## B. 中危修复

| # | 发现 | 修复 |
|---|---|---|
| B1 | 教师横向越权：任何教师可改/删其他教师账号密码、创建教师账号、改他人培训 | 账号与培训操作加归属校验（其他教师 → 403）；管理后台禁止创建教师账号（防提权）；培训 `PUT/DELETE/enroll/status` 仅创建者可操作 |
| B2 | 复习作答被写入「最后一条 attempt」（可能是已交卷的卷），污染考试记录与班级正确率 | 复习不再写 `answers` 表（掌握度/积分改由错题本自身状态驱动） |
| B3 | 错误响应透传内部信息（DSH 内网地址 `127.0.0.1:3090`、上游 API 原始报错） | 对外统一文案（"AI 服务暂时不可用"），细节只进服务端日志（4 处） |
| B4 | `/docs`、`/redoc`、`/openapi.json` 公网开放（匿名可枚举全部端点与模型） | 生产默认关闭（`FALLLEARN_ENABLE_DOCS=1` 才开）；SPA 回退对这三个路径返回 404；补 `Content-Security-Policy`（script/connect 仅同源）与 `Permissions-Policy` |
| B5 | 知识库文本 → 前端 `v-html` 未转义（存储型 XSS → 窃取 localStorage 中的 30 天 JWT） | 前端 `hi()` 改为**先 HTML 转义再做高亮**（关键词同步转义，`<mark>` 仍生效）；后端 `kb_doc` 加 realpath + 目录白名单双校验 |
| B6 | AI 直连 `base_url` 无白名单 → SSRF + API Key 可被导向任意主机（云元数据端点可窃取凭证） | 新增 `_validate_base_url()`：强制 http(s)、拦截 `169.254.0.0/16`（含 169.254.169.254）/`100.100.100.200`/multicast/unspecified（内网 LLM 网关仍允许，属合法教学场景） |
| B7 | check-then-insert 竞态产生 500（签到、开卷等） | 签到改 `INSERT OR IGNORE` + rowcount 判定；开卷捕获 `IntegrityError` |
| B8 | 口令无强度校验（空串/1 位可创建账号） | 新建/重置口径统一为 **6–128 位**（4 处入口） |
| B9 | 教师可控的 `link`/`image` 未做 scheme 校验（`javascript:`/`data:` 注入） | 白名单：`link` 仅站内 `/…` 或 http(s)；`image` 仅 `/uploads/…` 或 http(s) |
| B10 | AI 出题入库字段未校验（脏数据进入组卷池） | 白名单校验 qtype/cluster/难度/长度后才落库 |
| B11 | 登录节流内存表无界 + JWT `sub` 缺失可致 500 | 过期项自动淘汰（上限 2000）；`jwt.decode` 显式 `algorithms` + `require exp` + `sub` 缺失返回 401 |

## C. 依赖漏洞（第二轮）

| 包 | 原版本 | 漏洞 | 处置 |
|---|---|---|---|
| starlette | 0.50.0 | **10 条**（PYSEC-2026-161/248/249/2280/2281；含查询串二次方复杂度 DoS 等） | 升级 **fastapi 0.141.1 + starlette 1.7.0**（requirements.txt 显式锁定 starlette） |
| vite（devDependency） | 6.3.5 | **7 条**（GHSA-4w7w-66w2-5vf9 等，dev server 相关） | 升级 **vite 8.3.1 + @vitejs/plugin-vue 6.0.9**（构建产物复验通过） |

- 复扫：`pip-audit -r requirements.txt --vulnerability-service osv` → **No known vulnerabilities found**
- 前端：OSV npm batch 查询（vue/vue-router/vite/plugin-vue/esbuild/rollup/postcss）→ **HITS 0**
- Bandit 复扫：**0 HIGH / 0 MEDIUM**（9 LOW 为 DSH 中继的有意容错降级，已在首轮说明）

## D. 自动化验收（可复跑）

| 脚本 | 覆盖 | 结果 |
|---|---|---|
| `tools/security_check.py` | 26 项：请求体上限/口令强度/教师越权/SSRF/scheme/并发交卷幂等/复习防刷/扫描面 404/CSP | **26/26 通过** |
| `tools/ui_check.py` | 一键体验登录/答案朗读·复制/错题打印/知识库高亮与转义/移动端溢出/JS 异常 | **全过** |
| `tools/api_check_admin.py` | 管理后台 API 31 项 | **31/31 通过** |
| `tools/smoke_platform.py` | 页面渲染 + 移动端 390 溢出 + 守卫/404 | **SMOKE ALL PASS** |
| XSS 端到端探针 | 向知识库写入 `<img onerror>` 载荷文档 → 前端检索 → 载荷被转义为文本、脚本未执行（验证后删除探针） | **通过** |

## E. 仍接受的风险（不变）

| 风险 | 说明 |
|---|---|
| HTTP 明文（无 TLS） | 比赛周期内无域名/ICP 备案；登录已节流、数据面已限次、密码为演示账号。赛后上域名为 P0 |
| JWT 30 天有效期 | 演示场景可接受；停用账号即时生效（每次请求查库校验） |
| SQLite 单文件 | 比赛规模足够；WAL 已开；并发写入由唯一索引 + 条件更新兜底 |