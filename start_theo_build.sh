export BACKEND_PORT=8001
export FRONTEND_PORT=8081
export DB_PORT=5433
export ENV="theo"

docker compose -p theo_project up --build
#docker compose -p theo_project build --no-cache && docker compose -p theo_project up