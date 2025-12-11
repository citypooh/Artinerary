
// ========================================
// CSRF TOKEN HELPER
// ========================================
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// ========================================
// DELETE EXISTING IMAGE - GLOBAL FUNCTION
// ========================================
function deleteExistingImage(imageId, reviewId) {
    if (!confirm('Are you sure you want to delete this image?')) {
        return;
    }

    console.log('🗑️ Deleting image ID:', imageId);

    // FIXED: Correct URL path matching urls.py
    fetch('/loc_detail/api/image/' + imageId + '/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        }
    })
        .then(response => {
            console.log('Response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Response data:', data);
            if (data.success) {
                console.log('✅ Image deleted successfully');
                // Remove the image element from DOM
                const imageItem = document.querySelector('.existing-image-item[data-image-id="' + imageId + '"]');
                if (imageItem) {
                    imageItem.style.opacity = '0';
                    setTimeout(() => imageItem.remove(), 300);
                }
                alert('Image deleted successfully');
            } else {
                console.error('❌ Failed to delete:', data.error);
                alert(data.error || 'Failed to delete image');
            }
        })
        .catch(error => {
            console.error('❌ Error:', error);
            alert('An error occurred while deleting the image');
        });
}

// ========================================
// MAIN INITIALIZATION
// ========================================
document.addEventListener('DOMContentLoaded', function () {
    // ========================================
    // FAVORITE BUTTON
    // ========================================
    const favoriteBtn = document.getElementById('favorite-button');
    if (favoriteBtn) {
        favoriteBtn.addEventListener('click', function () {
            const artId = this.getAttribute('data-art-id');
            const favoriteText = document.getElementById('favorite-text');
            const heart = favoriteBtn.querySelector('.heart');

            fetch('/loc_detail/api/favorite/' + artId + '/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.favorited) {
                        heart.classList.add('favorited');
                        favoriteText.textContent = 'Remove from Favorites';
                        alert('Added to favorites');
                    } else {
                        heart.classList.remove('favorited');
                        favoriteText.textContent = 'Add to Favorites';
                        alert('Removed from favorites');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to update favorites');
                });
        });
    }

    // ========================================
    // REPLY BUTTONS
    // ========================================
    document.querySelectorAll('.reply-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const commentId = this.getAttribute('data-comment-id');
            const replyForm = document.getElementById('reply-form-' + commentId);
            if (replyForm) {
                replyForm.classList.toggle('active');
            }
        });
    });

    // ========================================
    // FIXED LIKE/DISLIKE FUNCTIONALITY
    // ========================================
    const reactionButtons = document.querySelectorAll('.reaction-btn');

    reactionButtons.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();

            if (this.disabled) {
                console.log('⏸️ Button disabled, ignoring click');
                return;
            }

            const commentId = this.getAttribute('data-comment-id');
            const reaction = this.getAttribute('data-reaction');

            console.log('🎯 Clicked:', reaction, 'on comment', commentId);

            // CRITICAL FIX: Find the CORRECT parent container
            // Use the closest review-item or reply-item
            const commentContainer = this.closest('.review-item, .reply-item');
            if (!commentContainer) {
                console.error('❌ Could not find comment container');
                return;
            }

            // Now find buttons WITHIN this specific container
            const allButtons = commentContainer.querySelectorAll('.reaction-btn[data-comment-id="' + commentId + '"]');
            let likeBtn = null;
            let dislikeBtn = null;

            allButtons.forEach(function (button) {
                if (button.getAttribute('data-reaction') === 'like') {
                    likeBtn = button;
                } else if (button.getAttribute('data-reaction') === 'dislike') {
                    dislikeBtn = button;
                }
            });

            if (!likeBtn || !dislikeBtn) {
                console.error('❌ Could not find like/dislike buttons');
                console.log('Like button:', likeBtn);
                console.log('Dislike button:', dislikeBtn);
                return;
            }

            const likeCountSpan = likeBtn.querySelector('.count');
            const dislikeCountSpan = dislikeBtn.querySelector('.count');

            if (!likeCountSpan || !dislikeCountSpan) {
                console.error('❌ Could not find count spans');
                return;
            }

            console.log('📊 Before - Likes:', likeCountSpan.textContent, 'Dislikes:', dislikeCountSpan.textContent);

            // Disable buttons during request
            likeBtn.disabled = true;
            dislikeBtn.disabled = true;

            // Make API call
            fetch('/loc_detail/api/comment/' + commentId + '/reaction', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrftoken
                },
                body: 'reaction=' + reaction
            })
                .then(function (response) {
                    console.log('📡 Response status:', response.status);
                    if (!response.ok) {
                        throw new Error('Server returned ' + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    console.log('📦 Response data:', data);

                    if (data.success) {
                        // ✅ UPDATE COUNTS IMMEDIATELY
                        likeCountSpan.textContent = data.likes;
                        dislikeCountSpan.textContent = data.dislikes;

                        // ✅ UPDATE ACTIVE STATES IMMEDIATELY
                        likeBtn.classList.remove('active');
                        dislikeBtn.classList.remove('active');

                        if (data.user_reaction === 'like') {
                            likeBtn.classList.add('active');
                        } else if (data.user_reaction === 'dislike') {
                            dislikeBtn.classList.add('active');
                        }

                        console.log('✨ Updated - Likes:', data.likes, 'Dislikes:', data.dislikes, 'User reaction:', data.user_reaction);
                    } else {
                        console.error('❌ Server returned success: false');
                        alert('Failed to update reaction');
                    }
                })
                .catch(function (error) {
                    console.error('❌ Error:', error);
                    alert('Failed to update reaction. Please try again.');
                })
                .finally(function () {
                    // Re-enable buttons
                    likeBtn.disabled = false;
                    dislikeBtn.disabled = false;
                    console.log('🔓 Buttons re-enabled');
                });
        });
    });

    // ========================================
    // IMAGE UPLOAD HANDLING
    // ========================================
    function setupImageUpload(singleId, multipleId, dropAreaId, previewId) {
        let selectedFiles = [];
        const maxFiles = 5;
        const maxFileSize = 5 * 1024 * 1024; // 5MB

        const singleUpload = document.getElementById(singleId);
        const multipleUpload = document.getElementById(multipleId);
        const dropArea = document.getElementById(dropAreaId);
        const preview = document.getElementById(previewId);

        if (!multipleUpload || !preview) {
            return;
        }

        // Single image upload
        if (singleUpload) {
            singleUpload.addEventListener('change', function (e) {
                const file = e.target.files[0];
                if (file && validateFile(file)) {
                    if (selectedFiles.length >= maxFiles) {
                        alert('Maximum ' + maxFiles + ' images allowed');
                        this.value = '';
                        return;
                    }
                    selectedFiles.push(file);
                    updatePreview();
                    updateMultipleInput();
                    this.value = '';
                }
            });
        }

        // Multiple images upload
        multipleUpload.addEventListener('change', function (e) {
            const newFiles = Array.from(e.target.files);

            if (selectedFiles.length + newFiles.length > maxFiles) {
                alert('You can only upload up to ' + maxFiles + ' images total');
                return;
            }

            for (const file of newFiles) {
                if (validateFile(file)) {
                    selectedFiles.push(file);
                }
            }

            updatePreview();
            updateMultipleInput();
        });

        // Drag and drop
        if (dropArea) {
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, preventDefaults, false);
            });

            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }

            ['dragenter', 'dragover'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.classList.add('highlight');
                });
            });

            ['dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.classList.remove('highlight');
                });
            });

            dropArea.addEventListener('drop', function (e) {
                const dt = e.dataTransfer;
                const files = Array.from(dt.files);

                for (const file of files) {
                    if (selectedFiles.length >= maxFiles) {
                        alert('Maximum ' + maxFiles + ' images allowed');
                        break;
                    }
                    if (validateFile(file)) {
                        selectedFiles.push(file);
                    }
                }

                updatePreview();
                updateMultipleInput();
            });
        }

        function validateFile(file) {
            if (!file.type.startsWith('image/')) {
                alert('"' + file.name + '" is not an image file');
                return false;
            }
            if (file.size > maxFileSize) {
                alert('Your uploaded file "' + file.name + '" is too large. Max size is 5MB');
                return false;
            }
            return true;
        }

        function updatePreview() {
            preview.innerHTML = '';

            selectedFiles.forEach((file, index) => {
                const reader = new FileReader();
                reader.onload = function (e) {
                    const imgPreview = document.createElement('div');
                    imgPreview.className = 'image-preview-item';

                    const prevImage = document.createElement('img');
                    prevImage.src = e.target.result;
                    prevImage.alt = 'Preview ' + (index + 1);

                    const deleteBtn = document.createElement('button');
                    deleteBtn.type = 'button';
                    deleteBtn.className = 'delete-image-btn';
                    deleteBtn.innerHTML = '×';
                    deleteBtn.onclick = function () {
                        selectedFiles.splice(index, 1);
                        updatePreview();
                        updateMultipleInput();
                    }

                    const counterDiv = document.createElement('div');
                    counterDiv.className = "counter";

                    imgPreview.appendChild(prevImage);
                    imgPreview.appendChild(deleteBtn);
                    imgPreview.appendChild(counterDiv);

                    preview.appendChild(imgPreview);
                }
                reader.readAsDataURL(file);
            });
        }

        function updateMultipleInput() {
            const dt = new DataTransfer();
            selectedFiles.forEach(file => dt.items.add(file));
            multipleUpload.files = dt.files;
        }

    }

    // Setup both upload forms
    setupImageUpload('images-upload-single', 'images-upload', 'drop-area', 'image-previews');
    setupImageUpload('edit-images-single', 'edit-images-multiple', 'edit-drop-area', 'edit-image-previews');

    // ========================================
    // REPORT BUTTONS
    // ========================================
    document.querySelectorAll('.report-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const commentId = this.getAttribute('data-comment-id');
            openReportModal(commentId);
        });
    });

    // ========================================
    // AUTO-EXPANDING TEXTAREAS
    // ========================================
    function autoExpandTextarea(textarea) {
        textarea.style.height = 'auto';
        const maxHeight = parseInt(getComputedStyle(textarea).maxHeight);
        textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px';
    }

    document.querySelectorAll('.review-textarea, .reply-textarea').forEach(textarea => {
        textarea.addEventListener('input', function () {
            autoExpandTextarea(this);
        });

        textarea.addEventListener('focus', function () {
            autoExpandTextarea(this);
        });
    });
});

// ========================================
// CANCEL REPLY
// ========================================
function cancelReply(commentId) {
    const replyForm = document.getElementById('reply-form-' + commentId);
    if (replyForm) {
        replyForm.classList.remove('active');
    }
}

// ========================================
// REPORT MODAL
// ========================================
let currentReportCommentId = null;

function openReportModal(commentId) {
    currentReportCommentId = commentId;
    document.getElementById('reportModal').classList.add('active');
    document.querySelectorAll('input[name="report_reason"]').forEach(cb => cb.checked = false);
    document.getElementById('additionalInfo').value = '';
}

function closeReportModal() {
    document.getElementById('reportModal').classList.remove('active');
    currentReportCommentId = null;
}

function submitReport() {
    const reasons = Array.from(document.querySelectorAll('input[name="report_reason"]:checked')).map(cb => cb.value);

    if (reasons.length === 0) {
        alert('Please select at least one reason');
        return;
    }

    const additionalInfo = document.getElementById('additionalInfo').value;
    const submitBtn = document.querySelector('.btn-submit-report');

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    fetch('/loc_detail/api/comment/' + currentReportCommentId + '/report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({
            reasons: reasons,
            additional_info: additionalInfo
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                closeReportModal();
            } else {
                alert(data.error || 'Failed to submit report');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred');
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Report';
        });
}

// ========================================
// IMAGE MODAL
// ========================================
function openImageModal(src) {
    document.getElementById('modalImage').src = src;
    document.getElementById('imageModal').classList.add('active');
}

function closeImageModal() {
    document.getElementById('imageModal').classList.remove('active');
}

// ========================================
// ADD TO ITINERARY
// ========================================
const addToItineraryBtn = document.getElementById('add-to-itinerary-button');
if (addToItineraryBtn) {
    addToItineraryBtn.addEventListener('click', function () {
        const artId = this.getAttribute('data-art-id');
        const artTitle = this.getAttribute('data-art-title');
        showAddToItineraryModal(artId, artTitle);
    });
}

function showAddToItineraryModal(locationId, locationTitle) {
    const modalHTML = '<div id="itinerary-modal" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; display: flex; align-items: center; justify-content: center;">' +
        '<div style="background: white; padding: 30px; border-radius: 10px; max-width: 500px; width: 90%; color: var(--page-background);">' +
        '<h3 style="margin-top: 0;">Add "' + locationTitle + '" to Itinerary</h3>' +
        '<div style="margin: 20px 0;">' +
        '<label style="display: block; margin-bottom: 10px;">Select an existing itinerary:</label>' +
        '<select id="existing-itinerary" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">' +
        '<option value="">Loading...</option>' +
        '</select>' +
        '</div>' +
        '<div style="text-align: center; margin: 15px 0; color: #666;">OR</div>' +
        '<div style="margin: 20px 0;">' +
        '<label style="display: block; margin-bottom: 10px;">Create a new itinerary:</label>' +
        '<input type="text" id="new-itinerary-title" placeholder="Enter itinerary name" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">' +
        '</div>' +
        '<div style="display: flex; gap: 10px;">' +
        '<button onclick="closeItineraryModal()" style="flex: 1; padding: 10px; background: #ddd; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">Cancel</button>' +
        '<button onclick="submitAddToItinerary(\'' + locationId + '\')" style="flex: 1; padding: 10px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">Add</button>' +
        '</div>' +
        '<div id="itinerary-message" style="margin-top: 15px; padding: 10px; border-radius: 5px; display: none;"></div>' +
        '</div>' +
        '</div>';

    const existingModal = document.getElementById('itinerary-modal');
    if (existingModal) existingModal.remove();

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    fetch('/itineraries/api/user-itineraries/')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('existing-itinerary');
            if (data.itineraries && data.itineraries.length > 0) {
                select.innerHTML = '<option value="">-- Select an itinerary --</option>' +
                    data.itineraries.map(itin => '<option value="' + itin.id + '">' + itin.title + ' (' + itin.stop_count + ' stops)</option>').join('');
            } else {
                select.innerHTML = '<option value="">No itineraries yet</option>';
            }
        });
}

window.closeItineraryModal = function () {
    const modal = document.getElementById('itinerary-modal');
    if (modal) modal.remove();
};

window.submitAddToItinerary = function (locationId) {
    const existingItineraryId = document.getElementById('existing-itinerary').value;
    const newItineraryTitle = document.getElementById('new-itinerary-title').value.trim();
    const messageDiv = document.getElementById('itinerary-message');

    if (!existingItineraryId && !newItineraryTitle) {
        messageDiv.textContent = 'Please select an itinerary or create a new one';
        messageDiv.style.display = 'block';
        messageDiv.style.background = '#fee';
        messageDiv.style.color = '#c00';
        return;
    }

    const formData = new FormData();
    formData.append('location_id', locationId);
    if (newItineraryTitle) {
        formData.append('new_itinerary_title', newItineraryTitle);
    } else {
        formData.append('itinerary_id', existingItineraryId);
    }

    fetch('/itineraries/api/add-to-itinerary/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                messageDiv.textContent = data.message;
                messageDiv.style.display = 'block';
                messageDiv.style.background = '#efe';
                messageDiv.style.color = '#060';
                setTimeout(() => closeItineraryModal(), 1500);
            } else {
                messageDiv.textContent = data.error || 'Failed to add';
                messageDiv.style.display = 'block';
                messageDiv.style.background = '#fee';
                messageDiv.style.color = '#c00';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            messageDiv.textContent = 'An error occurred';
            messageDiv.style.display = 'block';
            messageDiv.style.background = '#fee';
            messageDiv.style.color = '#c00';
        });
};

// ========================================
// EDIT COMMENT
// ========================================
const editForm = document.querySelector('.review-edit');
const [editButton] = document.querySelectorAll('.btn-edit-comment');
editButton.addEventListener('click', () => {
    editForm.hidden = !editForm.hidden;
})