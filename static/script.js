$(document).ready(function () {
    // Handle form submissions
    $("form").on("submit", function (event) {
        event.preventDefault(); // Prevent the default form submission
        const form = $(this);
        const url = form.attr("action");
        const method = form.attr("method");

        // Get the logged-in user's Unique ID from the session
        const loggedInUserId = "{{ session.get('user_id') }}";

        // Get the Unique ID entered in the form
        const formUserId = form.find("input[name='id_number'], input[name='update_id'], input[name='delete_id'], input[name='delete_driver_id']").val();

        // Validate the Unique ID (only for non-admin users)
        if (!"{{ session.get('is_admin') }}" && formUserId !== loggedInUserId) {
            showAlert("You can only use your own Unique ID Number.", "error");
            return; // Stop the form submission
        }

        // Send the form data using AJAX
        $.ajax({
            type: method,
            url: url,
            data: form.serialize(), // Serialize the form data
            success: function (response) {
                showAlert(response.message, "success");
            },
            error: function (xhr) {
                
                // Handle errors
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    showAlert(xhr.responseJSON.message, "error");
                } else {
                    showAlert("An error occurred. Please try again.", "error");
                }
            }
        });
    });

    // Show forms based on dashboard option clicks
    $(".dashboard-options a").on("click", function (e) {
        e.preventDefault();
        const target = $(this).data("target");
        $(".form-container").hide(); // Hide all forms
        $(target).show(); // Show the selected form
    });
});

function showAlert(message, type) {
    const alertBox = $(".alert");
    alertBox.text(message);
    alertBox.css("background-color", type === "success" ? "rgba(0, 255, 0, 0.8)" : "rgba(255, 0, 0, 0.8)");
    alertBox.show();
    setTimeout(function () {
        alertBox.hide();
    }, 3000);
}