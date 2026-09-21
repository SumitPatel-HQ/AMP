FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_AMIS_API_URL=http://localhost:8000
ENV VITE_AMIS_API_URL=${VITE_AMIS_API_URL}
RUN npm run build:bundle

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
