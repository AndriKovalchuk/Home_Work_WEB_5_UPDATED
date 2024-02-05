import asyncio
import logging
from datetime import datetime, timedelta
import httpx
import websockets
import names
from rich.console import Console
from rich.text import Text
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK
from aiofile import async_open
from rich.table import Table


logging.basicConfig(level=logging.INFO)


async def logging_to_file(command):
    async with async_open("log.txt", "a") as file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await file.write(f'{timestamp}: Received "{command}" command\n')


async def request(url: str) -> dict | str:
    try:
        async with httpx.AsyncClient() as client:  # we have a session
            r = await client.get(url, timeout=60)
            if r.status_code == 200:
                result = r.json()
                return result
            else:
                return "Couldn't get the exchange rates."
    except httpx.ReadTimeout:
        return "HTTP request timed out."
    except Exception as e:
        return f"Error during HTTP request: {str(e)}"


async def get_exchange(days: int = None):
    console = Console()
    response = await request(
        f"https://api.privatbank.ua/p24api/exchange_rates?date=01.12.2014"
    )

    current_date = datetime.now().date()
    if not days:

        table = Table(title='Contacts list', title_style='bold')
        table.add_column('Currency')
        table.add_column('Sale')
        table.add_column('Purchase')

        result = f"{current_date.strftime('%d.%m.%Y')}:\n"

        exchange_rates = [val for val in response['exchangeRate']]

        for val_dict in exchange_rates:
            if val_dict.get('saleRate') is not None:
                currency = val_dict.get('currency')
                exchange_dict = {"sale": val_dict.get("saleRate"), "purchase": val_dict.get("purchaseRate")}

                #format_ = f"{currency}: sale: {exchange_dict.get('sale')}, purchase: {exchange_dict.get('purchase')}\n"
                #result += format_

                table.add_row(Text(currency),
                              Text(str(exchange_dict.get('sale'))),
                              Text(str(exchange_dict.get('purchase'))))

        await logging_to_file('exchange')
        return table


    else:
        delta = timedelta(days=days)
        delta_1 = timedelta(days=1)
        check_date = current_date - delta
        new_list = []
        while check_date <= (current_date - delta_1):
            result = f'{check_date.strftime('%d.%m.%Y')}: '
            response = await request(
                "https://api.privatbank.ua/p24api/exchange_rates?date=" + check_date.strftime("%d.%m.%Y")
            )

            exchange_rates = [val for val in response['exchangeRate']]

            for val_dict in exchange_rates:

                currency = val_dict.get("currency")
                if val_dict.get("saleRate") is not None:
                    exchange_dict = {
                        "sale": val_dict.get("saleRate"),
                        "purchase": val_dict.get("purchaseRate"),
                    }

                    format_ = (f"{currency}: "
                               f"sale: {exchange_dict.get('sale')}, "
                               f"purchase: {exchange_dict.get('purchase')}; ")
                    result += format_

            new_list.append(result)
            check_date += delta_1
        result = "\n".join(new_list)
        await logging_to_file(f'"exchange {days}"')
        return result


class Server:
    clients = set()  # Clients who joined the server
    console = Console()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)  # Adding a client to set 'clients'
        logging.info(f"{ws.remote_address} connects")

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)  # Removes the client from the set
        logging.info(f"{ws.remote_address} disconnects")

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distribute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def distribute(self, ws: WebSocketServerProtocol):
        commands = [
            "exchange 1",
            "exchange 2",
            "exchange 3",
            "exchange 4",
            "exchange 5",
            "exchange 6",
            "exchange 7",
            "exchange 8",
            "exchange 9",
            "exchange 10",
        ]
        async for message in ws:
            if message.lower().strip() == "exchange":
                exchange = await get_exchange()
                await self.send_to_clients(exchange)
            elif message.lower().strip() in commands:
                days = int(message.split()[-1])
                exchange = await get_exchange(days)
                await self.send_to_clients(exchange)
            elif message.lower().strip() == "Hello server":
                await self.send_to_clients("Hi everyone!")
            else:
                await self.send_to_clients(f"{ws.name}: {message}")


# Realization of websocket package
async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, "localhost", 8080):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
