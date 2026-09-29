# 第二轮全面评测报告（性能 / 兼容性 / 无障碍 / UX）

- 日期：2026-09-29 深夜（P1.1 之后）
- 范围：前端（20 个 SFC + 1 套样式表）、后端（13 个模块）、静态资源与传输、浏览器端真实走查
- 工具：新增 `tools/perf_audit.py`（性能与健壮性）、`tools/ux_audit.py`（UX/兼容性/无障碍），配合既有 8 套验收脚本

## 一、结论摘要

| 维度 | 关键指标 | 结果 |
|---|---|---|
| 接口延迟（16 个只读接口，各 5 次） | p50 中位数最高 30ms，无 ≥300ms | 优秀 |
| 传输压缩 | JS 61%、CSS 77%（gzip，`Content-Length` 实测） | 优秀 |
| 首屏 | TTFB 17ms / FCP 220ms / DCL 142ms；首屏传输 65KB（解压 161KB） | 优秀 |
| 二次访问 | 传输 7.9KB（hashed 资源 `immutable` 长缓存命中） | 优秀 |
| 并发（16 并发 × 40 请求 × 3 接口） | 错误 0/120，p95 ≤ 128ms | 优秀 |
| 横向溢出 | 6 种视口（360/390/768/1024/1440/1920）× 8 个学生页 = 48 组 | 全部 0 溢出 |
| 键盘可达性 | Tab 顺序、焦点可见、回车提交 | 通过 |
| 打印 | 导航/按钮自动隐藏（导出 PDF 场景） | 通过 |
| 触控目标 | 390 宽下 ≥32px | 通过（1 处 30px 在容差内） |
| 文本对比度 | WCAG AA（正文 4.5 / 大字 3.0） | 通过 |
| 降级 | `prefers-reduced-motion` 过渡归零 | 通过 |
| JS 异常 | 全流程 0 异常、0 404 资源 | 通过 |

## 二、发现并修复的问题（10 项）

| # | 问题（评测发现的原始现象） | 影响 | 修复 |
|---|---|---|---|
| 1 | **无 favicon**：`/favicon.svg`、`/favicon.ico` 404（控制台报错、标签页无图标） | 品牌完整性与"工程质量"观感 | 新增 `public/favicon.svg`（品牌红圆角 + "跌"字），`index.html` 声明 icon / theme-color / description |
| 2 | **登录页密码框不在 `<form>` 内**（Chrome 明确提示 "Password field is not contained in a form"） | 密码管理器/自动填充支持差，回车提交依赖手工 keyup | 登录表单重构为 `<form @submit.prevent>`，输入框补 `name/autocomplete/id + label for`，主按钮 `type="submit"`，体验按钮显式 `type="button"` |
| 3 | **首屏白屏**：Vue 挂载前 `#app` 全空 | 弱网/低端机第一印象 | `index.html` 内置轻量占位 + `<noscript>` 提示（挂载后自动替换，不污染布局） |
| 4 | **360px 宽横向溢出 25px**（知识库页标签行 `nowrap`）：`.pills` 不换行、`.kcount` 被挤出 | 小屏手机出现横向滚动 | `.pills { flex-wrap: wrap; row-gap: 8px }` |
| 5 | **移动端触控目标偏小**：实测 20 个元素 <32px（退出 26、签到 24、朗读/复制 23、重答/讲解 26、去看看 31） | 手机误触、演示不顺手 | 640px 断点统一放大 `.btn.sm`/`.pill`/`.chip`/`.navtabs a`/`.op`/`.gc-close`/`.b-cta`/`.checkin-row .btn-sm`；结果 20 → 1（30px） |
| 6 | **品牌红作文字色对比度不足**：#e4393c 白底 4.24:1（<AA 4.5），共 61 处文字色 | 可读性/无障碍不达标 | 新增 `--primary-text:#c62828`（5.9:1）替换文字色；误改的 29 处 `border-color` 已回归 `--primary` |
| 7 | **填充色承载白字对比度不足**：#e4393c 白字 4.24、#f5a623 白字 2.03、#22c55e 白字 2.28、#0ea5e9 白字 2.77 | 按钮/标签/簇封面白字偏虚 | 新增 `--primary-deep:#cf2a2a`（白字 5.2）用于 8 处红色填充；6 个知识簇配色整体加深（`#3B82F6→#2563EB`、`#22C55E→#15803D`、`#E4393C→#CF2A2A`、`#F5A623→#B45309`、`#8B5CF6→#6D28D9`、`#0EA5E9→#0369A1`） |
| 8 | **次要文字对比度略差**：`.slogan`/`.stu-badge` 4.46、灰底小字 4.12 | AA 边缘 | `--text-3` 由 `#6f7887` 加深为 `#5f6875`（白底 5.5、灰底 5.1）；`.pill` 默认文字色提到 `--text-3` |
| 9 | **`HEAD` 请求 405**（`curl -I`、云监控、负载均衡健康检查常用） | 运维友好性 | `spa` 与 `/api/health` 改为 `methods=["GET","HEAD"]`（Starlette 自动丢弃 HEAD 响应体） |
| 10 | **学习报告查询存在临时排序**（`attempts` 按 student_id+status 过滤再按 submitted_at 排序） | 数据规模化后的排序开销 | 新增复合索引 `idx_attempts_student_status(student_id, status, submitted_at)`（迁移自动建立） |

> 说明：评测脚本首版有 3 处"假阳性/假阴性"，已一并修正并在脚本内注明，避免后续误判：
> ① `requests` 会自动解压 gzip，压缩率须用 `Content-Length` 计算（否则误报"压缩率 0%"）；
> ② 对比度检测须排除 Banner（深色渐变背景取不到真实底色）、纯 emoji 图标、WCAG 大字（≥18.66px 或 ≥14px 粗体，标准 3.0）；
> ③ 回车登录断言不能在同一页面先做 Tab 走查、也不能注入 `history` hook（两者会干扰表单提交测量）。

## 三、未改动的项（评估后决定保持）

| 项 | 评估 |
|---|---|
| `points_cache` / `users` 小表全表扫描 | 表仅 2–4 行，SQLite 选择扫描优于索引；脚本已改为"仅大表（>500 行）告警" |
| DB 中 `CREATE UNIQUE INDEX` 语句看似重复 | 实为 `try / except IntegrityError`（先去重再重建）的重试分支，**设计正确**，不可"去重" |
| `vite` 产物体积（318KB / 35 文件，首屏 3 文件 133KB） | 已属优秀区间，不做人为拆分；hashed 长期缓存 + gzip 后首屏仅 65KB |
| AI 问答首字延迟 | 取决于外部模型网关，非前端/后端代码问题 |

## 四、复跑方式（佐证材料）

```powershell
D:\python123\python.exe E:\lilei\platform\tools\perf_audit.py      # 性能与健壮性（本机或远程）
D:\python123\python.exe E:\lilei\platform\tools\ux_audit.py        # UX/兼容性/无障碍
D:\python123\python.exe E:\lilei\platform\tools\ui_check.py        # 界面与转义
D:\python123\python.exe E:\lilei\platform\tools\security_check.py  # 安全加固 26 项
D:\python123\python.exe E:\lilei\platform\tools\api_check_admin.py # 管理 API 31 项
D:\python123\python.exe E:\lilei\platform\tools\smoke_platform.py  # 冒烟 + 移动端
D:\python123\python.exe E:\lilei\platform\tools\remote_readonly_check.py  # 部署后远程只读验收
```

**本轮实测结果**：`ux_audit` 失败 0 项 · `ui_check` 全过 · `security_check` 26/26 · `api_check_admin` 31/31 ·
`smoke_platform` ALL PASS · `perf_audit` 无失败项 · `remote_readonly_check` 失败 0 项。
