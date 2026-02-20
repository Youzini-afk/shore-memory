package main

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"

	perolink "github.com/YoKONCy/PeroLink/proto"
	"github.com/gorilla/websocket"
	goproto "google.golang.org/protobuf/proto"
)

var (
	authToken string
)

func generateAndSaveToken() {
	// 检查环境变量中的固定令牌 (适用于云/Docker部署)
	envToken := os.Getenv("GATEWAY_TOKEN")
	if envToken != "" {
		authToken = envToken
		log.Printf("🔑 使用环境变量中的固定 Gateway 令牌: %s", authToken)
	} else {
		// 定义保存令牌的路径: 默认为 data/gateway_token.json (Docker/本地相对路径)
		// 可以通过环境变量覆盖以支持旧版开发环境
		path := os.Getenv("GATEWAY_TOKEN_PATH")
		if path == "" {
			path = filepath.Join("data", "gateway_token.json")
		}

		// 生成随机令牌
		b := make([]byte, 32)
		_, err := rand.Read(b)
		if err != nil {
			log.Fatal("生成令牌失败:", err)
		}
		authToken = base64.URLEncoding.EncodeToString(b)
		log.Printf("🔑 已生成新的 Gateway 访问令牌: %s", authToken)

		// 确保目录存在
		dir := filepath.Dir(path)
		if err := os.MkdirAll(dir, 0755); err != nil {
			log.Printf("警告: 无法创建数据目录: %v", err)
		}

		data := map[string]string{
			"token": authToken,
		}
		fileData, _ := json.MarshalIndent(data, "", "  ")

		absPath, _ := filepath.Abs(path)
		if err := os.WriteFile(path, fileData, 0644); err != nil {
			log.Printf("警告: 无法保存令牌到文件 %s: %v", absPath, err)
		} else {
			log.Printf("✅ Gateway 令牌已保存至: %s", absPath)
		}
	}
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // 暂时允许所有跨域来源
	},
}

// Node 代表一个已连接的客户端
type Node struct {
	ID   string
	Conn *websocket.Conn
	mu   sync.Mutex
	// 能力集等
}

// Hub 维护活跃节点集合
type Hub struct {
	nodes map[string]*Node
	mu    sync.RWMutex
}

var hub = &Hub{
	nodes: make(map[string]*Node),
}

func (h *Hub) removeNodeByConn(conn *websocket.Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	for id, node := range h.nodes {
		if node.Conn == conn {
			delete(h.nodes, id)
			// log.Printf("节点 %s 已断开连接", id)
			break
		}
	}
}

func main() {
	generateAndSaveToken()
	http.HandleFunc("/ws", handleWebSocket)
	log.Println("PeroGateway 已启动，端口 :14747")
	if err := http.ListenAndServe(":14747", nil); err != nil {
		log.Fatal("监听服务失败 (ListenAndServe):", err)
	}
}

func handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("WebSocket 升级失败 (upgrade):", err)
		return
	}
	defer conn.Close()
	defer hub.removeNodeByConn(conn)

	// log.Println("新连接来自", r.RemoteAddr)

	for {
		messageType, p, err := conn.ReadMessage()
		if err != nil {
			// 如果是正常关闭，不打印错误日志
			if !websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				break
			}
			log.Println("读取消息失败 (read):", err)
			break
		}

		if messageType != websocket.BinaryMessage {
			log.Println("期待二进制消息 (Protobuf)")
			continue
		}

		// 解码信封 (Envelope)
		var envelope perolink.Envelope
		if err := goproto.Unmarshal(p, &envelope); err != nil {
			log.Println("反序列化失败 (unmarshal):", err)
			continue
		}

		handleEnvelope(conn, &envelope)
	}
}

func handleEnvelope(conn *websocket.Conn, envelope *perolink.Envelope) {
	// 默认只记录错误或警告，或使用调试标志
	// fmt.Printf("收到信封: ID=%s Source=%s Target=%s\n", envelope.Id, envelope.SourceId, envelope.TargetId)

	// 处理 Hello 握手消息
	if hello := envelope.GetHello(); hello != nil {
		handleHello(conn, envelope.SourceId, hello)
	}

	// 处理心跳消息
	if hb := envelope.GetHeartbeat(); hb != nil {
		// fmt.Printf("来自 %s 的心跳: seq=%d (ts=%d)\n", envelope.SourceId, hb.Seq, envelope.Timestamp)
		return // 心跳消息不转发
	}

	// 路由逻辑
	if envelope.TargetId == "broadcast" {
		broadcastMessage(envelope)
	} else if envelope.TargetId != "master" {
		unicastMessage(envelope)
	}
}

func broadcastMessage(envelope *perolink.Envelope) {
	hub.mu.RLock()
	defer hub.mu.RUnlock()

	data, err := goproto.Marshal(envelope)
	if err != nil {
		log.Println("序列化错误 (marshal error):", err)
		return
	}

	for id, node := range hub.nodes {
		if id == envelope.SourceId {
			continue // 不回显给发送者
		}

		node.mu.Lock()
		err := node.Conn.WriteMessage(websocket.BinaryMessage, data)
		node.mu.Unlock()
		if err != nil {
			log.Printf("发送至 %s 错误: %v\n", id, err)
			// TODO: 处理断开连接
		}
	}
}

func unicastMessage(envelope *perolink.Envelope) {
	hub.mu.RLock()
	defer hub.mu.RUnlock()

	node, ok := hub.nodes[envelope.TargetId]
	if !ok {
		log.Printf("目标节点 %s 未找到\n", envelope.TargetId)
		return
	}

	data, err := goproto.Marshal(envelope)
	if err != nil {
		log.Println("序列化错误 (marshal error):", err)
		return
	}

	node.mu.Lock()
	err = node.Conn.WriteMessage(websocket.BinaryMessage, data)
	node.mu.Unlock()
	if err != nil {
		log.Printf("发送至 %s 错误: %v\n", envelope.TargetId, err)
	}
}

func handleHello(conn *websocket.Conn, sourceID string, hello *perolink.Hello) {
	// log.Printf("收到来自 %s 的 Hello (设备: %s, 平台: %s)\n", sourceID, hello.DeviceName, hello.Platform)

	// 验证令牌
	if hello.Token != authToken {
		log.Printf("⚠️  来自 %s 的令牌无效: %s (预期: %s)", sourceID, hello.Token, authToken)
		// log.Println("⚠️  鉴权失败 (为了迁移兼容继续执行...)")
	} else {
		// log.Println("✅ 鉴权成功")
	}

	hub.mu.Lock()
	hub.nodes[sourceID] = &Node{
		ID:   sourceID,
		Conn: conn,
	}
	hub.mu.Unlock()

	// log.Printf("节点 %s 已注册", sourceID)
}
