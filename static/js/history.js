function confirmDelete(storyId, deleteUrl) {
    Swal.fire({
        title: 'Are you sure?',
        text: "You won't be able to revert this!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Yes, delete it!',
        background: '#222',
        color: '#fff',
        customClass: {
            confirmButton: 'swal-font',
            cancelButton: 'swal-font',
            title: 'swal-font',
            htmlContainer: 'swal-font'
        }
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(deleteUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ story_id: storyId })
            }).then(response => response.json()).then(data => {
                if (data.success) {
                    const storyElement = document.getElementById(`story-${storyId}`);
                    if (storyElement) {
                        storyElement.remove();
                    }
                    Toastify({
                        text: "Story deleted successfully!",
                        duration: 3000,
                        close: true,
                        gravity: "top",
                        position: "right",
                        style: {
                            background: "linear-gradient(to right, #00b09b, #96c93d)",
                            fontFamily: "'Press Start 2P', cursive"
                        }
                    }).showToast();
                } else {
                    console.error('Failed to delete story.');
                    Toastify({
                        text: "Failed to delete story: " + data.error,
                        duration: 3000,
                        close: true,
                        gravity: "top",
                        position: "right",
                        style: {
                            background: "linear-gradient(to right, #ff5f6d, #ffc371)",
                            fontFamily: "'Press Start 2P', cursive"
                        }
                    }).showToast();
                }
            });
        }
    });
}

function showFlashedMessages(flashedMessages) {
    if (flashedMessages) {
        for (var i = 0; i < flashedMessages.length; i++) {
            var category = flashedMessages[i][0];
            var message = flashedMessages[i][1];
            Toastify({
                text: message,
                duration: 3000,
                close: true,
                gravity: "top",
                position: "right",
                style: {
                    background: category === 'success' ? 'linear-gradient(to right, #00b09b, #96c93d)' : 'linear-gradient(to right, #ff5f6d, #ffc371)',
                    fontFamily: '"Press Start 2P", cursive'
                }
            }).showToast();
        }
    }
}
