console.log("Racaal Platform loaded successfully.");


/* =========================
   TELEGRAM CONTROL CENTER
========================= */

function openSection(section) {

    const element = document.getElementById(section);

    if (element) {
        element.scrollIntoView({
            behavior: "smooth"
        });
    }
}


/* =========================
   TELEGRAM MENU
========================= */

function showTelegram(section) {

    const pages = document.querySelectorAll(".tg-page");

    pages.forEach(function(page) {
        page.classList.remove("active");
    });


    const selectedPage = document.getElementById("tg-" + section);

    if (selectedPage) {
        selectedPage.classList.add("active");
    }


    const menuButtons =
        document.querySelectorAll(".telegram-menu");

    menuButtons.forEach(function(button) {
        button.classList.remove("active");
    });


    menuButtons.forEach(function(button) {

        const onclickValue =
            button.getAttribute("onclick");

        if (onclickValue &&
            onclickValue.includes("'" + section + "'")) {

            button.classList.add("active");
        }

    });

}


/* =========================
   DEMO BUTTONS
========================= */

document.addEventListener("DOMContentLoaded", function() {

    const buttons =
        document.querySelectorAll(
            ".service-card button, " +
            ".platform-card button, " +
            ".login-btn"
        );


    buttons.forEach(function(button) {

        button.addEventListener("click", function(event) {

            const text =
                button.textContent.trim();

            if (
                text.includes("Coming Soon") ||
                text === "Login"
            ) {

                event.preventDefault();

                alert(
                    "This Racaal feature will be connected during the next development stage."
                );

            }

        });

    });

});
