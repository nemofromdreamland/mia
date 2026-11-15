"""WebSocket echo agent, copied from the official AWS docs (task 0.7). See README.md."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


@app.websocket
async def websocket_handler(websocket, context):
    """Simple echo WebSocket handler."""
    await websocket.accept()

    try:
        data = await websocket.receive_json()
        # Echo back
        await websocket.send_json({"echo": data})
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await websocket.close()


if __name__ == "__main__":
    app.run(log_level="info")
