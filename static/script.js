// Function to bind event handlers
function bindEventHandlers() {
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
        console.log("Dropdown link clicked"); // Debugging statement
        const target = $(this).data("target");
        console.log("Target form:", target); // Debugging statement
        $(".form-container").hide(); // Hide all forms
        $(target).show(); // Show the selected form
    });
}

// Function to show alerts
function showAlert(message, type) {
    const alertBox = $(".alert");
    alertBox.text(message);
    alertBox.css("background-color", type === "success" ? "rgba(0, 255, 0, 0.8)" : "rgba(255, 0, 0, 0.8)");
    alertBox.show();
    setTimeout(function () {
        alertBox.hide();
    }, 3000);
}

// Bind event handlers when the document is ready
$(document).ready(function () {
    bindEventHandlers();
});

// Re-bind event handlers when the page is loaded via AJAX or navigation
$(window).on("load", function () {
    bindEventHandlers();
});