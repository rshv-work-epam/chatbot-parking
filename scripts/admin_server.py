from chatbot_parking.web_demo_server import app


if __name__ == "__main__":
    import uvicorn

    # Bind to 0.0.0.0 so port forwarding (e.g., Codespaces/Dev Containers) can reach it
    uvicorn.run(app, host="0.0.0.0", port=8000)
