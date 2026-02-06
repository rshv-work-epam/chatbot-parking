"""CLI entrypoint for the parking chatbot demo."""

from chatbot_parking.chatbot import ParkingChatbot
from chatbot_parking.orchestration import run_demo


def run() -> None:
    chatbot = ParkingChatbot()
    print(chatbot.answer_question("What are the working hours and location?"))
    workflow_state = run_demo()
    print("Admin decision:", workflow_state.admin_decision)


if __name__ == "__main__":
    run()
