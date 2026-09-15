# AgentRun 控制台实操：示例应用

这是导入自己 Codeup 仓库的应用源码包，不是容器镜像，也不是完整流水线。
只在获准的内部渠道分发；整理为代码包不代表获得对外公开授权。

## 如何放入 Codeup

1. 在自己的云效组织中创建一个代码库。
2. 在电脑上解压代码包。
3. 使用 Codeup 网页文件上传功能，将解压目录内的文件放入仓库，保留 app、tests 目录结构。
4. 如果上传界面不支持目录，则先在网页创建对应目录，再逐个上传文件。
5. 确认仓库根目录直接显示 Dockerfile、requirements.txt、app，而不是再套一层“示例代码包”目录。
6. 提交到 master 分支。仅上传 ZIP 文件本身不能构建。

## 基础镜像与共享 ACR

Dockerfile 使用本教程已有的共享 ACR 基础镜像，固定了 Tag 和 SHA256，并改用公网域名。
这个 ACR 域名不是密钥，但仓库仍然是私有的：公网可达不等于匿名可拉取。
构建前须在自己的 Flow 配置有权读取共享 ACR 的服务连接，并由 ACR 管理员放行构建集群实际出口 IP。
如果向该 ACR 推送应用镜像，还需要目标仓库的推送权限。
若没有共享实例访问授权，请先联系资源提供方，不要直接运行。
本次仅打包，未重新验证共享基础镜像在云端是否仍存在、是否可拉取。
不要将 FROM 随意换为另一个应用镜像，以免重复创建用户或引入未知依赖。

## 创建 AgentRun 时填写

- 启动端口：9000。
- 启动命令：python -m uvicorn app.main:app --host 0.0.0.0 --port 9000 --proxy-headers --loop asyncio --http h11 --lifespan off
- DASHSCOPE_API_KEY：你自己的百炼 API Key，仅在运行时配置，不要提交仓库。
- QWEN_MODEL：填写自己账号可用的模型；本教程此前验证使用 qwen3.8-flash。
- DASHSCOPE_BASE_URL：填写与 API Key 对应地域的 OpenAI 兼容地址，代码默认 https://dashscope.aliyuncs.com/compatible-mode/v1。

应用访问百炼需要出网。入站认证应在 AgentRun 配置 API Key 等鉴权；
应用本身没有实现调用者鉴权，不要直接匿名暴露到公网。
入站 API Key、百炼 API Key、RAM 发布 AK 是三种不同凭证，不可混用。

## 接口

- GET /health：只检查应用存活，不证明模型调用成功。
- POST /invocations（同时支持 / 和 /v1/chat/completions）。

请求示例：

```json
{"messages":[{"role":"user","content":"请只回复 AGENTRUN_OK"}],"stream":false,"max_tokens":256}
```

模型由运行时 QWEN_MODEL 决定，请求中的 model 不会覆盖它。

## 包含与不包含

包含应用源码、Dockerfile、依赖声明和使用模拟模型响应的单元测试。
不包含真实密钥、Git 历史、原环境 RAM 身份、Runtime ID、服务连接 ID 或自动发布脚本。
依赖声明沿用示例版本范围，未锁定精确版本；后续正式维护应固定已验证的依赖。
流水线将在教程后续步骤创建，不要把此包视为已完成 CI/CD。

开发者可安装 requirements-dev.txt 后运行 pytest；测试不会调用真实百炼，也不会产生模型费用。
