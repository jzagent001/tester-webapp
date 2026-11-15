import uvicorn


def main() -> None:
    uvicorn.run("app.main:app", reload=True)


if __name__ == "__main__":
    main()
