document.addEventListener('DOMContentLoaded', () => {
    const notificationButton = document.getElementById('notificationButton');
    const notificationList = document.getElementById('notificationList');

    notificationButton.addEventListener('click', () => {
        fetch('/notifications')
            .then(response => response.json())
            .then(data => {
                notificationList.innerHTML = '';
                data.notifications.forEach(notification => {
                    const li = document.createElement('li');
                    li.classList.add('list-group-item');
                    li.innerHTML = `${notification.message} <small>${notification.timestamp}</small>`;
                    notificationList.appendChild(li);
                });
            });
    });
});
