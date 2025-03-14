$(document).ready(function () {
    // Handle form submissions
    $("form").on("submit", function (event) {
        event.preventDefault(); // Prevent the default form submission
        const form = $(this);
        const url = form.attr("action");
        const method = form.attr("method");

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

    // Show forms based on dropdown selection
    $(".dropdown-content a").on("click", function (e) {
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


$(document).ready(function () {
    // Function to show alert
    function showAlert(message, type) {
        const alertBox = $('.alert');
        alertBox.text(message).addClass(type).fadeIn();

        // Hide the alert after 5 seconds
        setTimeout(function () {
            alertBox.fadeOut();
        }, 5000);
    }

    // Handle form submissions
    $('form').on('submit', function (e) {
        e.preventDefault(); // Prevent default form submission

        const form = $(this);
        const action = form.attr('action');
        const method = form.attr('method');
        const data = form.serialize();

        // Send AJAX request
        $.ajax({
            url: action,
            type: method,
            data: data,
            success: function (response) {
                // Show success alert
                showAlert(response.message, 'success');
            },
            error: function (xhr) {
                // Show error alert
                showAlert(xhr.responseJSON.message, 'error');
            }
        });
    });
});