from sender import Sender
import asyncio
import json

async def main():
    PRIVATE_KEY = input("Enter private key: ")
    PROXY = input("Enter proxy: ")
    TO_ADDRESS = input("Enter address to: ")

    with open("chains.json") as file:
        chains: {} = json.load(file)

    is_valid_chain_name: bool = False
    is_valid_token: bool = False
    is_valid_amount: bool = False

    chain_name: str = ""
    token_name: str = ""
    amount: float = 0

    while not is_valid_chain_name:
        chain_name = input(f"Choose chains: {dict(chains).keys()}: ")
        chain_name = chain_name.lower().strip()
        is_valid_chain_name = chain_name in chains

    selected_chain: {} = chains.get(chain_name)

    while not is_valid_token:
        token_name = input(f"Choose token: {dict(selected_chain).get("tokens").keys()}: ")
        token_name = token_name.lower().strip()
        is_valid_token = token_name in selected_chain.get("tokens")

    want_send_all = input(f"Do you want to send all {token_name}? Enter 'yes' or 'no'")

    send_all: bool = "yes" in want_send_all.lower().strip()

    if not send_all:
        while not is_valid_amount:
            amount_str = input(f"Enter amount of {token_name}: ")

            try:
                amount = float(amount_str)
            except ValueError:
                print("Amount is not a numer")

            is_valid_amount = amount > 0

    sender = Sender(
        private_key=PRIVATE_KEY,
        proxy=PROXY,
        chain=selected_chain
    )

    balance = await sender.get_token_balance(token_name)
    print(f"Balance: {balance:.3f} {token_name}")

    if send_all:
        amount = balance

    if amount > balance:
        print(f"There are insufficient {token_name} in your account: ")

    hax_bytes_trx = await sender.send(amount=amount, to=TO_ADDRESS, token=token_name)

    if hax_bytes_trx is None:
        print("Transaction not sent, try again")
        return

    print(f"Transaction sent: {hax_bytes_trx.hex()}")

    await sender.wait_tx(hex_bytes=hax_bytes_trx)

try:
    asyncio.run(main())
except Exception as e:
    print(f"Shit happened: {e}")
