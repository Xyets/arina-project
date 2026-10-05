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
   WEBSOCKET
   RULES UPDATE
===================================================== */

let obsSocket = null;
let obsReconnectTimer = null;


/* =====================================================
   PROFILE KEY
===================================================== */

const profileKey =
    document.body.dataset.profileKey;


/* =====================================================
   CONNECT
===================================================== */

function connectObsWebSocket() {

    if (!profileKey) {
        console.error(
            "FlowTip OBS: profile_key not found"
        );

        return;
    }


    if (
        obsSocket &&
        (
            obsSocket.readyState === WebSocket.OPEN
            ||
            obsSocket.readyState === WebSocket.CONNECTING
        )
    ) {
        return;
    }


    obsSocket = new WebSocket(
        "wss://arinairina.duckdns.org/ws/"
    );


    obsSocket.onopen = function() {

        console.log(
            "FlowTip OBS: WebSocket connected"
        );


        obsSocket.send(
            JSON.stringify({

                type: "hello",

                role: "obs",

                profile_key: profileKey

            })
        );

    };


    obsSocket.onmessage = function(event) {

        try {

            const data =
                JSON.parse(event.data);


            /*
             * Сервер сообщает,
             * что правила изменились.
             */

            if (
                data.rules_update
                &&
                (
                    !data.profile_key
                    ||
                    data.profile_key === profileKey
                )
            ) {

                refreshRulesFromWebSocket();

            }

        } catch (error) {

            console.error(
                "FlowTip OBS WS message error:",
                error
            );

        }

    };


    obsSocket.onclose = function() {

        console.log(
            "FlowTip OBS: WebSocket disconnected"
        );


        clearTimeout(
            obsReconnectTimer
        );


        obsReconnectTimer =
            setTimeout(
                connectObsWebSocket,
                3000
            );

    };


    obsSocket.onerror = function(error) {

        console.error(
            "FlowTip OBS WebSocket error:",
            error
        );

    };

}


/* =====================================================
   REFRESH MENU
   CALLED ONLY AFTER rules_update
===================================================== */

async function refreshRulesFromWebSocket() {

    try {

        const separator =
            window.location.href.includes("?")
                ? "&"
                : "?";


        const url =
            window.location.href
            + separator
            + "_flowtip_ws_refresh="
            + Date.now();


        const response =
            await fetch(
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


        if (
            !newCard
            ||
            !currentCard
        ) {

            return;

        }


        /*
         * Меняем только содержимое меню.
         *
         * Саму страницу не перезагружаем.
         */

        currentCard.replaceWith(
            newCard
        );


        /*
         * После изменения правил
         * заново запускаем пагинацию.
         */

        initializePagination();


        console.log(
            "FlowTip OBS: rules updated"
        );


    } catch (error) {

        console.error(
            "FlowTip OBS rules refresh error:",
            error
        );

    }

}


/* =====================================================
   START
===================================================== */

connectObsWebSocket();