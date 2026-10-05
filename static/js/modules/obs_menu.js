/* =====================================================
   FLOWTIP OBS MENU
   PAGINATION + AUTO UPDATE
===================================================== */


/* =====================================================
   PAGINATION TIMERS
===================================================== */

let paginationTimers = [];


/* =====================================================
   CLEAR TIMERS
===================================================== */

function clearPaginationTimers() {

    paginationTimers.forEach(function(timer) {

        clearInterval(timer);

    });

    paginationTimers = [];
}


/* =====================================================
   SETUP PAGINATION
===================================================== */

function setupPagination(options) {

    const pages = Array.from(
        document.querySelectorAll(
            options.pageSelector
        )
    );


    const dots = Array.from(
        document.querySelectorAll(
            options.dotSelector
        )
    );


    const counter = document.querySelector(
        options.counterSelector
    );


    if (!pages.length) {
        return;
    }


    let currentPage = 0;


    /* =========================================
       SHOW PAGE
    ========================================= */

    function showPage(index) {

        currentPage =
            (index + pages.length)
            % pages.length;


        pages.forEach(function(page, i) {

            page.classList.toggle(
                "active",
                i === currentPage
            );

        });


        dots.forEach(function(dot, i) {

            dot.classList.toggle(
                "active",
                i === currentPage
            );

        });


        if (counter) {

            if (pages.length > 1) {

                counter.textContent =
                    (currentPage + 1)
                    + " / "
                    + pages.length;

            } else {

                counter.textContent = "";

            }

        }

    }


    /* =========================================
       FIRST PAGE
    ========================================= */

    showPage(0);


    /* =========================================
       ONLY ONE PAGE
    ========================================= */

    if (pages.length <= 1) {
        return;
    }


    /* =========================================
       AUTO CHANGE
    ========================================= */

    const timer = setInterval(
        function() {

            showPage(
                currentPage + 1
            );

        },
        4500
    );


    paginationTimers.push(timer);


    /* =========================================
       DOT CLICK
    ========================================= */

    dots.forEach(function(dot, index) {

        dot.addEventListener(
            "click",
            function() {

                showPage(index);

            }
        );

    });

}


/* =====================================================
   INITIALIZE PAGINATION
===================================================== */

function initializePagination() {

    clearPaginationTimers();


    /* VIBRATION */

    setupPagination({

        pageSelector:
            ".vibration-page",

        dotSelector:
            "#vibrationPagination .dot",

        counterSelector:
            "#vibrationCounter"

    });


    /* ACTIONS */

    setupPagination({

        pageSelector:
            ".action-page",

        dotSelector:
            "#actionPagination .dot",

        counterSelector:
            "#actionCounter"

    });

}


/* =====================================================
   INITIAL LOAD
===================================================== */

initializePagination();


/* =====================================================
   CHECK FOR RULE CHANGES
=====================================================

   Каждые 10 секунд страница спрашивает
   сервер:

       "Правила изменились?"

   Если изменились:
       меню обновляется.

   Если нет:
       ничего не происходит.
===================================================== */

async function refreshRules() {

    try {

        const separator =
            window.location.href.includes("?")
                ? "&"
                : "?";


        const url =
            window.location.href
            + separator
            + "_flowtip_refresh="
            + Date.now();


        const response = await fetch(
            url,
            {
                cache: "no-store"
            }
        );


        if (!response.ok) {
            return;
        }


        const html =
            await response.text();


        const parser =
            new DOMParser();


        const newDocument =
            parser.parseFromString(
                html,
                "text/html"
            );


        const newCard =
            newDocument.querySelector(
                ".menu-card"
            );


        const currentCard =
            document.querySelector(
                ".menu-card"
            );


        if (!newCard || !currentCard) {
            return;
        }


        /* =========================================
           RULES DID NOT CHANGE
        ========================================= */

        if (
            newCard.innerHTML.trim()
            === currentCard.innerHTML.trim()
        ) {

            return;
        }


        /* =========================================
           RULES CHANGED
        ========================================= */

        currentCard.replaceWith(
            newCard
        );


        /* =========================================
           START PAGINATION AGAIN
        ========================================= */

        initializePagination();


    } catch (error) {

        /*
         * Если сервер временно недоступен,
         * ничего страшного.
         *
         * Старое меню продолжает работать.
         */

        console.log(
            "FlowTip menu refresh:",
            error
        );

    }

}


/* =====================================================
   AUTO REFRESH
===================================================== */

setInterval(
    refreshRules,
    10000
);