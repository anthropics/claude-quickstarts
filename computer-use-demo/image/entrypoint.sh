#!/bin/bash
set -e

# Port configuration with defaults
# These are the ports the services listen on INSIDE the container.
# When using custom Docker port mappings (e.g. -p 9090:8080), set the
# corresponding HOST_PORT variables to the host-side port numbers so the
# browser can reach each service correctly.
export HTTP_PORT="${HTTP_PORT:-8080}"
export STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
export VNC_PORT="${VNC_PORT:-5900}"
export NOVNC_PORT="${NOVNC_PORT:-6080}"

# Host-side ports (what the browser connects to). Default to matching the
# container ports, which is correct when using symmetric port mappings like
# -p 8080:8080. Override these when the host port differs from the container
# port, e.g. -e STREAMLIT_HOST_PORT=9501 when using -p 9501:8501.
export HTTP_HOST_PORT="${HTTP_HOST_PORT:-$HTTP_PORT}"
export STREAMLIT_HOST_PORT="${STREAMLIT_HOST_PORT:-$STREAMLIT_PORT}"
export NOVNC_HOST_PORT="${NOVNC_HOST_PORT:-$NOVNC_PORT}"

./start_all.sh
./novnc_startup.sh

# Generate the landing page with the configured host ports so the browser
# can reach the Streamlit and noVNC iframes regardless of how Docker ports
# are mapped on the host.
cat > static_content/index.html << HTMLEOF
<!doctype html>
<html>
    <head>
        <title>Computer Use Demo</title>
        <meta name="permissions-policy" content="fullscreen=*" />
        <style>
            body {
                margin: 0;
                padding: 0;
                overflow: hidden;
            }
            .container {
                display: flex;
                height: 100vh;
                width: 100vw;
            }
            .left {
                flex: 1;
                border: none;
                height: 100vh;
            }
            .right {
                flex: 2;
                border: none;
                height: 100vh;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <iframe
                src="http://localhost:${STREAMLIT_HOST_PORT}"
                class="left"
                allow="fullscreen"
            ></iframe>
            <iframe
                id="vnc"
                src="http://localhost:${NOVNC_HOST_PORT}/vnc.html?&resize=scale&autoconnect=1&view_only=1&reconnect=1&reconnect_delay=2000"
                class="right"
                allow="fullscreen"
            ></iframe>
            <button
                id="toggleViewOnly"
                style="position: absolute; top: 10px; right: 10px; z-index: 1000"
            >
                Toggle Screen Control (Off)
            </button>
            <script>
                document
                    .getElementById("toggleViewOnly")
                    .addEventListener("click", function () {
                        var vncIframe = document.getElementById("vnc");
                        var button = document.getElementById("toggleViewOnly");
                        var currentSrc = vncIframe.src;
                        if (currentSrc.includes("view_only=1")) {
                            vncIframe.src = currentSrc.replace(
                                "view_only=1",
                                "view_only=0",
                            );
                            button.innerText = "Toggle Screen Control (On)";
                        } else {
                            vncIframe.src = currentSrc.replace(
                                "view_only=0",
                                "view_only=1",
                            );
                            button.innerText = "Toggle Screen Control (Off)";
                        }
                    });
            </script>
        </div>
    </body>
</html>
HTMLEOF

HTTP_PORT=$HTTP_PORT python http_server.py > /tmp/server_logs.txt 2>&1 &

STREAMLIT_SERVER_PORT=$STREAMLIT_PORT python -m streamlit run computer_use_demo/streamlit.py > /tmp/streamlit_stdout.log &

echo "Computer Use Demo is ready!"
echo "Open http://localhost:${HTTP_HOST_PORT} in your browser to begin"

# Keep the container running
tail -f /dev/null
