FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV VITE_API_ORIGIN=http://localhost:8000 VITE_API_URL=http://localhost:8000/api
RUN npm run build -- --base /
FROM caddy:2-alpine
COPY --from=build /app/dist /usr/share/caddy
