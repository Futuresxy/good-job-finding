# Good Job Finding

面向 2027 届秋招的岗位情报与个性化匹配项目，重点覆盖 AI Infra、芯片设计、计算机体系结构、编译器与异构计算。

## 当前能力

- 按专业方向、技能关键词、目标城市和重点公司筛选岗位
- 区分提前批、人才计划、正式批与专项计划
- 记录岗位职责、任职要求、投递时间、招聘流程和官方来源
- 已核验岗位提供直接投递链接；`applyUrl` 必须指向具体岗位或招聘项目页面，不能只填公司首页
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

微信通道使用腾讯微信 ClawBot 与 OpenClaw 的扫码连接，不需要 URL、Webhook 或 Token。

在运行 OpenClaw 的设备执行：

```bash
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
```

随后使用微信扫描终端展示的二维码，启用微信 ClawBot 插件。微信 ClawBot 仅接收 OpenClaw 在 24 小时窗口内的回复，因此每日任务应由 OpenClaw 按固定时间读取 `data/notifications.json` 并在有效窗口内回复。仓库不保存二维码、微信 Cookie、会话凭证或聊天内容。

详细步骤见 `docs/openclaw-weixin.md`。

## GitHub Pages

在仓库 Settings → Pages 中将 Source 设置为 GitHub Actions。部署后地址预计为：

https://futuresxy.github.io/good-job-finding/

## 数据可信度

示例记录统一标记为“待核验”。采集器上线后只把具备官方招聘页或官方公告证据的信息标记为“已开启”。页面不可访问时保留上次状态，并标记为“本次未确认”，避免误报关闭。

## 招聘源校正与自定义公司

网站“重点公司与招聘源”区域会显示仓库中的默认官方招聘网址。可以先在浏览器中修改网址并保存；点击“同步每日监测”后，会打开一个预填好的 GitHub Issue。由仓库所有者提交后，工作流会校验请求，并自动更新 `config/sources.json` 与 `config/profile.json`，随后该公司进入每日监测。

为避免公开仓库被他人篡改，自动入库只处理仓库所有者创建、标题以 `[招聘源]` 开头的 Issue。
