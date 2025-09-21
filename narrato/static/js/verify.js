const messagesDiv = document.getElementById('flash-messages');
const messagesData = messagesDiv.getAttribute('data-messages');
if (messagesData) {
    const messages = JSON.parse(messagesData);
    if (messages) {
        messages.forEach(function(message) {
            Toastify({
                text: message[1],
                duration: 3000,
                close: true,
                gravity: "top",
                position: "right",
                style: {
                    background: 'linear-gradient(to right, #ff5f6d, #ffc371)',
                    fontFamily: '"Press Start 2P", cursive'
                }
            }).showToast();
        });
    }
}
