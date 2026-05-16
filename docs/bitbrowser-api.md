# 比特浏览器 (BitBrowser) API 接口文档

> 来源: https://doc2.bitbrowser.cn
> 下载日期: 2026-05-09
> Local Server 默认地址: http://127.0.0.1:54345

---

## 接口通用说明

- 所有接口 Method 均为 **POST**
- 传参方式: body 传参, **JSON 格式** (不是 form-data, 不是 url 参数)
- 返回: JSON 对象, `success: true` 表示成功, 数据在 `data` 中
- 失败: `success: false`, 错误信息在 `msg` 中

```json
// 成功示例
{"success": true, "data": {"id": "xxx", "groupName": "test"}}

// 失败示例
{"success": false, "msg": "分组id必传"}
```

---

## 一、健康检查

### POST /health
测试 Local Server 是否连接成功, 无参数

```json
{"success": true}
```

---

## 二、浏览器窗口接口

### POST /browser/update — 创建/修改窗口

创建窗口时 `browserFingerPrint` 对象必传 (可传空 `{}` 随机生成)

**关键参数:**

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| groupId | string | 是 | 分组ID, 不传则自动创建API分组 |
| name | string | 否 | 窗口名称 |
| platform | string | 否 | 平台URL, 如 https://x.com |
| url | string | 否 | 额外打开的URL, 多个逗号连接 |
| remark | string | 否 | 备注信息 |
| proxyMethod | number | 是 | 2=自定义, 3=提取IP |
| proxyType | string | 否 | http/https/socks5/ssh |
| host | string | 否 | 代理主机 |
| port | number | 否 | 代理端口 |
| proxyUserName | string | 否 | 代理用户名 |
| proxyPassword | string | 否 | 代理密码 |
| cookie | string | 否 | JSON格式cookie |
| browserFingerPrint | object | 是 | 指纹对象 (见下方) |

**browserFingerPrint 指纹对象:**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| coreProduct | chrome | 内核: chrome / firefox |
| coreVersion | 130 | Chrome内核版本 |
| ostype | PC | PC / Android / IOS |
| os | Win32 | Win32 / MacIntel / Linux x86_64 |
| osVersion | "" | 操作系统版本 |
| webRTC | "3" | 0=替换, 1=允许, 2=禁止, 3=隐私 |
| canvas | "0" | 0=随机, 1=关闭 |
| webGL | "0" | 0=随机, 1=关闭 |
| audioContext | "0" | 0=随机, 1=关闭 |
| hardwareConcurrency | "4" | 硬件并发数 |
| deviceMemory | "8" | 设备内存 (不要>8) |
| openWidth | 1280 | 窗口宽度 |
| openHeight | 720 | 窗口高度 |
| launchArgs | "" | 启动参数, 逗号分隔 |

**创建示例:**
```json
{
  "name": "windows browser",
  "proxyMethod": 2,
  "proxyType": "socks5",
  "host": "1.2.3.4",
  "port": 1020,
  "proxyUserName": "abc",
  "proxyPassword": "def",
  "browserFingerPrint": {
    "coreVersion": "130",
    "ostype": "PC",
    "os": "Win32",
    "osVersion": "11,10"
  }
}
```

---

### POST /browser/update/partial — 批量修改窗口字段

只传需要更新的字段 + ids 数组

```json
{
  "ids": ["id1", "id2"],
  "name": "新名称",
  "groupId": "分组ID"
}
```

---

### POST /browser/open — 打开浏览器窗口

```json
{"id": "窗口ID", "args": [], "queue": true}
```

**args 有用参数:**
- `--remote-debugging-address=0.0.0.0` — 放通局域网端口
- `--headless` — 无头模式
- `--incognito` — 隐私模式
- `--load-extension=path1,path2` — 加载扩展

**返回:**
```json
{
  "success": true,
  "data": {
    "ws": "ws://127.0.0.1:53325/devtools/browser/xxx",
    "http": "127.0.0.1:53325",
    "coreVersion": "112",
    "pid": 31295,
    "seq": 3474,
    "name": "",
    "groupId": "xxx"
  }
}
```

---

### POST /browser/close — 关闭浏览器窗口

```json
{"id": "窗口ID"}
```
> ⚠️ 调用后等待 5 秒再操作 (让进程完全退出)

---

### POST /browser/closing/reset — 重置窗口关闭状态

窗口异常关闭后, API 提示"正在打开/关闭中"时使用

```json
{"id": "窗口ID"}
```

---

### POST /browser/delete — 彻底删除窗口 (不可恢复)

```json
{"id": "窗口ID"}
```

---

### POST /browser/detail — 获取窗口详情

```json
{"id": "窗口ID"}
```

返回完整窗口信息 (指纹、代理、状态等)

---

### POST /browser/list — 分页获取窗口列表

```json
{"page": 0, "pageSize": 10}
```
> page 从 0 开始, 一次最多 100 条

---

### POST /browser/pids — 批量获取窗口进程PID

```json
{"ids": ["id1", "id2"]}
```

返回: `{id: pid}` 映射, 可用于判断窗口是否已打开

---

### POST /browser/pids/all — 获取所有已打开窗口的PID

无参数, 自动过滤已死进程

---

### POST /browser/pids/alive — 检查窗口进程是否存活

```json
{"ids": ["id1", "id2"]}
```

---

### POST /browser/close/byseqs — 通过序号批量关闭

```json
{"seqs": [12, 13]}
```

---

### POST /browser/close/all — 关闭所有窗口

无参数

---

### POST /browser/delete/ids — 批量删除 (最多100个)

```json
{"ids": ["id1", "id2"]}
```

---

## 三、批量代理/分组/备注

### POST /browser/proxy/update — 批量修改代理

```json
{
  "ids": ["id1"],
  "proxyMethod": 2,
  "proxyType": "socks5",
  "host": "1.2.3.4",
  "port": 1020,
  "proxyUserName": "user",
  "proxyPassword": "pass"
}
```

### POST /browser/group/update — 批量修改分组

```json
{"groupId": "分组ID", "browserIds": ["id1", "id2"]}
```

### POST /browser/remark/update — 批量修改备注

```json
{"remark": "备注", "browserIds": ["id1", "id2"]}
```

---

## 四、窗口排列

### POST /windowbounds — 排列窗口+调整尺寸

```json
{
  "type": "box",
  "startX": 0, "startY": 0,
  "width": 500, "height": 400,
  "col": 3,
  "spaceX": 50, "spaceY": 50,
  "ids": ["id1", "id2"]
}
```

### POST /windowbounds/flexable — 一键自适应排列

```json
{"seqlist": []}
```

---

## 五、Cookie 管理

### POST /browser/cookies/set — 设置实时Cookie
### POST /browser/cookies/get — 获取实时Cookie
### POST /browser/cookies/clear — 清空Cookie
### POST /browser/cookies/format — 格式化Cookie

---

## 六、缓存清理

### POST /cache/clear — 清理窗口缓存 (所有)
### POST /cache/clear/exceptExtensions — 保留扩展数据清理

```json
{"ids": ["id1", "id2"]}
```

---

## 七、其他

### POST /checkagent — 代理检测
### POST /browser/fingerprint/random — 随机指纹
### POST /browser/ports — 获取所有已打开窗口的调试端口
### POST /alldisplays — 获取显示器列表
### POST /rpa/run — 执行RPA任务
### POST /rpa/stop — 停止RPA任务
