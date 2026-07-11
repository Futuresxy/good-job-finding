# OpenClaw 与微信 ClawBot 连接

本项目的微信推送不使用 Webhook URL、Token 或其他远程凭证。连接仅在运行 OpenClaw 的设备上通过微信扫码完成。

## 1. 安装并连接

在运行 OpenClaw 的设备执行：

\`\`\`bash
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
\`\`\`

安装过程会展示二维码。使用需要接收招聘提醒的微信扫描二维码，启用微信 ClawBot 插件。

## 2. 数据入口

招聘雷达每日生成：

\`\`\`text
https://raw.githubusercontent.com/Futuresxy/good-job-finding/main/data/notifications.json
\`\`\`

该文件包含新发现的官方页面线索、岗位变化和推送状态。具体岗位的展示与投递入口位于：

\`\`\`text
https://futuresxy.github.io/good-job-finding/
\`\`\`

## 3. OpenClaw 每日任务说明

在 OpenClaw 中建立每天固定运行的任务，任务目标如下：

> 每天 08:00 和 20:00 读取 Good Job Finding 的 notifications.json。只处理尚未发送的新事件；优先关注 AI Infra、LLM 推理系统、芯片设计、计算机体系结构、编译器与异构计算，以及重点公司。输出公司、招聘批次、岗位、地点、匹配理由、截止时间、变化摘要和具体投递链接。没有新事件时不发送。微信 ClawBot 仅接收 OpenClaw 24 小时内的回复，发送前确认当前会话仍在有效回复窗口内。

OpenClaw 的实际任务创建界面或命令可能随部署方式不同，以当前设备上的 OpenClaw 说明为准。

## 4. 测试清单

- 微信已成功扫码并能与 OpenClaw 双向收发消息。
- OpenClaw 能读取公开的 \`notifications.json\`。
- 同一个事件不会重复推送。
- “已开启”岗位包含具体 \`applyUrl\`，消息中的按钮或链接能直达投递页。
- 待核验线索明确标注，不当作已开启岗位推送。
- 在 24 小时回复窗口外不尝试强制发送。

## 5. 隐私边界

- 二维码、Cookie、会话凭证和聊天记录不进入 GitHub。
- 简历默认只在浏览器本地分析，不发送到 OpenClaw 或微信。
- 如需微信端使用简历匹配结果，只发送方向标签与匹配分数，不发送简历原文。
