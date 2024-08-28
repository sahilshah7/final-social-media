function deletePost(postId) {
  fetch(`/delete-post/${postId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
    }
  }).then(response => {
    if (response.ok) {
      location.reload();
    } else {
      alert('Error deleting post');
    }
  });
}

function likePost(postId) {
  fetch(`/like-post/${postId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
    }
  }).then(response => {
    if (response.ok) {
      location.reload();
    } else {
      alert('Error liking post');
    }
  });
}
