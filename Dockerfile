FROM golang:1.27-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -buildvcs=false -ldflags="-s -w" -o lokerscraper ./cmd/server

FROM alpine:3.20

WORKDIR /app

RUN apk --no-cache add ca-certificates tzdata

COPY --from=builder /app/lokerscraper .
COPY static ./static

EXPOSE 5000

CMD ["./lokerscraper"]
