#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
PORT="${NODE_PORT:-8224}"
BASE_URL="http://localhost:${PORT}"

on_interrupt() {
    echo ""
    echo "Stopping containers..."
    docker compose -f "$COMPOSE_FILE" down
    exit 130
}
trap on_interrupt INT TERM

remove_images() {
    echo ""
    echo "Removing images..."
    local image_name
    local image
    image_name="$(docker compose -f "$COMPOSE_FILE" config --images 2>/dev/null || true)"
    while IFS= read -r image; do
        if [[ -n "$image" ]]; then
            echo "Found image: $image"
            docker rmi -f "$image" 2>/dev/null || true
        fi
    done <<< "$image_name"
    for image in $(docker images --format "{{.Repository}}:{{.Tag}}" | grep -i "blockchain" || true); do
        echo "Found image: $image"
        docker rmi -f "$image" 2>/dev/null || true
    done
    echo "Images removed."
}

wait_for_health() {
    local waited=0
    while ! curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; do
        sleep 1
        waited=$((waited + 1))
        if [[ $waited -ge 60 ]]; then
            echo "The educational node did not answer ${BASE_URL}/health within 60s."
            echo "Check logs with: docker compose -f ${COMPOSE_FILE} logs"
            return 1
        fi
    done
}

start_service() {
    echo "Starting the educational node..."
    docker compose -f "$COMPOSE_FILE" up --build -d
    wait_for_health
}

show_banner() {
    echo "========================================"
    echo " Blockchain educational node"
    echo "========================================"
    echo " edu-node    ${BASE_URL}    (container port 8000)"
    echo "========================================"
}

show_running() {
    echo ""
    echo "Services are running"
    echo "  API:      ${BASE_URL}"
    echo "  API docs: ${BASE_URL}/docs"
    echo "  Health:   ${BASE_URL}/health"
}

show_menu() {
    echo ""
    echo "=============================="
    echo "  [k] stop, keep images and the chain volume"
    echo "  [q] stop and remove images, keep the chain volume"
    echo "  [v] full cleanup (images, volume, and host .runtime)"
    echo "  [r] restart"
    echo "=============================="
}

show_banner
start_service
show_running
show_menu

while true; do
    read -rp "Enter selection (k/q/v/r): " CHOICE
    CHOICE="$(printf '%s' "$CHOICE" | tr '[:upper:]' '[:lower:]')"
    case "$CHOICE" in
        k)
            echo ""
            echo "Stopping containers..."
            docker compose -f "$COMPOSE_FILE" down
            echo "Done."
            exit 0
            ;;
        q)
            echo ""
            echo "Stopping containers..."
            docker compose -f "$COMPOSE_FILE" down --remove-orphans
            remove_images
            echo "Done."
            exit 0
            ;;
        v)
            echo ""
            echo "Stopping containers and removing volumes..."
            docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans
            remove_images
            rm -rf .runtime
            echo "Done."
            exit 0
            ;;
        r)
            echo ""
            echo "Restarting..."
            docker compose -f "$COMPOSE_FILE" down
            start_service
            show_running
            show_menu
            ;;
        *)
            echo "Invalid selection. Enter k, q, v, or r."
            show_menu
            ;;
    esac
done
