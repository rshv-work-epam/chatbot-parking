"""Static knowledge base for the parking chatbot."""

STATIC_DOCUMENTS = [
    {
        "id": "parking_overview",
        "text": (
            "Our parking facility is located at 101 Main Street, near the city center. "
            "We support hourly and daily reservations and offer 24/7 CCTV monitoring."
        ),
        "sensitivity": "public",
    },
    {
        "id": "booking_process",
        "text": (
            "To reserve a space, provide your name, surname, car number, and the desired "
            "reservation period. A human administrator confirms each booking."
        ),
        "sensitivity": "public",
    },
    {
        "id": "payments",
        "text": (
            "Payment is accepted by card or mobile wallet at the kiosk or via the mobile app."
        ),
        "sensitivity": "public",
    },
]
