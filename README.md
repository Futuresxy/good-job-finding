# Good Job Finding

面向 2027 届秋招的岗位情报与个性化匹配项目，重点覆盖 AI Infra、芯片设计、计算机体系结构、编译器与异构计算。

## 当前能力

- 按专业方向、技能关键词、目标城市和重点公司筛选岗位
- 区分提前批、人才计划、正式批与专项计划
- 记录岗位职责、任职要求、投递时间、招聘流程和官方来源
- 支持浏览器本地上传简历并做关键词覆盖、岗位匹配和面试准备分析
- 支持自定义重点公司与通知偏好
- 为 Slack、OpenClaw + 微信、企业微信等推送渠道预留标准事件输出
- GitHub Actions 每日更新数据并自动发布 GitHub Pages

## 隐私说明

简历分析默认只在浏览器中完成，文件不会上传到仓库或第三方服务。当前支持文本型 PDF、TXT 和 Markdown；PDF 文本提取使用浏览器端 PDF.js。扫描版 PDF 需要先进行 OCR。

## 本地运行

\`\`\`bash
python -m http.server 8000
\`\`\`

访问 \`http://localhost:8000\`。

## 数据更新

\`\`\`bash
python scripts/update_jobs.py
\`\`\`

脚本读取 \`config/sources.json\`，更新 \`data/jobs.json\` 和 \`data/status.json\`。新增公司优先通过配置完成。正式接入公司官网时，应遵守网站条款、robots.txt 与合理访问频率；“已开启”状态必须保留官方证据链接。

## 微信推送

推荐使用 OpenClaw 与微信连接。系统生成的 \`data/notifications.json\` 可作为 OpenClaw 的输入，由 OpenClaw 在微信允许的 24 小时回复窗口内推送。首次连接或授权失效时需要用户扫码，不在仓库中保存二维码、Cookie 或个人凭证。

建议在 GitHub Actions Secrets 中配置：

- \`OPENCLAW_WEBHOOK_URL\`
- \`OPENCLAW_WEBHOOK_TOKEN\`

## GitHub Pages

在仓库 Settings → Pages 中将 Source 设置为 GitHub Actions。部署后地址预计为：

https://futuresxy.github.io/good-job-finding/

## 数据可信度

示例记录统一标记为“待核验”。采集器上线后只把具备官方招聘页或官方公告证据的信息标记为“已开启”。页面不可访问时保留上次状态，并标记为“本次未确认”，避免误报关闭。
