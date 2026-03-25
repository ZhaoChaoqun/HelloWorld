# HTTP/2 多连接 + RST_STREAM 测试

## 测试场景

模拟真实的HTTP/2客户端行为：
- ✅ 启用 `EnableMultipleHttp2Connections = true`（允许建立多个TCP连接）
- ✅ 客户端**监控每个stream的响应速度**
- ✅ 当检测到某个stream响应慢（超过2秒），**主动发送RST_STREAM**中止该stream
- ✅ 服务器接收RST_STREAM并取消请求处理

> **注意**：这不是超时机制，而是客户端主动监控并决定放弃慢速stream

## 工作原理

### 🔹 EnableMultipleHttp2Connections 的作用
- 默认情况下，HttpClient对同一域名只使用1个HTTP/2连接（复用多个stream）
- 启用后，允许建立多个并发的HTTP/2连接（每个连接可以有多个stream）
- 当某个连接的stream出现问题时，可以通过其他连接继续工作

### 🔹 客户端行为
```
1. 发起 /slow 请求
2. 启动计时器，监控响应时间
3. 如果2秒内没有响应：
   - 调用 CancellationToken.Cancel()
   - 底层发送 HTTP/2 RST_STREAM 帧
   - 中止该stream
4. 同时可以继续发送其他请求（多连接特性）
```

### 🔹 服务器行为
```
1. 接收请求，开始处理（耗时10秒）
2. 如果收到 RST_STREAM：
   - HttpContext.RequestAborted 被触发
   - 抛出 OperationCanceledException
   - 停止处理并记录日志
```

## 运行测试

### 步骤1：启动服务器
```bash
cd /Users/zhaochaoqun/repos/HelloWorld/Http2SlowServer
dotnet run
```

### 步骤2：运行客户端（新终端窗口）
```bash
cd /Users/zhaochaoqun/repos/HelloWorld/Http2ClientTester
dotnet run
```

## 预期结果

### 客户端日志示例：
```
Client #0: Starting /slow request...
Client #1: Starting /slow request...
Client #0: ⚠️ Stream too slow (2000ms), sending RST_STREAM...
Client #0: ❌ RST_STREAM sent after 2001ms (stream cancelled)
Client: /fast ✅ OK
Client #1: ⚠️ Stream too slow (2000ms), sending RST_STREAM...
```

### 服务器日志示例：
```
Server [Conn:a1b2c3d4]: 🐌 Slow request started (will take ~10s)
Server [Conn:a1b2c3d4]: Processing... 1/10
Server [Conn:a1b2c3d4]: Processing... 2/10
Server [Conn:a1b2c3d4]: ❌ RST_STREAM received from client (request aborted)
```

## 关键点

| 特性 | 说明 |
|------|------|
| **多连接** | `EnableMultipleHttp2Connections = true` 允许多个TCP连接 |
| **非超时** | 不是HttpClient的Timeout，而是客户端主动监控决策 |
| **RST_STREAM** | HTTP/2协议帧，用于中止单个stream而不影响连接 |
| **服务器感知** | 通过 `HttpContext.RequestAborted` 检测到客户端中止 |
| **实时监控** | 客户端每个请求都有独立的计时器监控响应速度 |

## 技术细节

- **客户端发送20个慢请求 + 若干快请求**
- **慢请求在2秒后被检测为"太慢"，发送RST_STREAM**
- **快请求正常完成，证明连接池工作正常**
- **服务器端显示连接ID，可观察是否使用了多个连接**
