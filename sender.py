from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.types import TxParams, Wei, HexBytes, HexStr, ChecksumAddress
from web3.exceptions import TransactionNotFound
from web3.contract import AsyncContract
from typing import cast
import asyncio
import json

class Sender:
    w3: AsyncWeb3
    address_from: ChecksumAddress
    private_key: str
    chain: {}
    abi: any

    def __init__(self, *, private_key, proxy: str, chain: {}):
        self.private_key = private_key
        self.chain = chain

        request_kwargs = {
            "proxy": f"http://{proxy}"
        } if proxy else {}

        self.__load_abi()
        self.w3 = AsyncWeb3(AsyncHTTPProvider(chain.get("rpc_url"), request_kwargs=request_kwargs))
        self.address_from = self.w3.to_checksum_address(self.w3.eth.account.from_key(self.private_key).address)

    def __load_abi(self):
        with open(self.chain.get("abi")) as file:
            self.abi = json.load(file)

    def to_wei(self, *, amount: float, decimals: int):
        unit_name = {
            6: "mwei",
            9: "gwei",
            18: "ether",
        }.get(decimals)

        if not unit_name:
            raise RuntimeError(f"Can`t find unit for decimals: {decimals}")

        return self.w3.to_wei(amount, unit_name)

    async def __send(self, transaction: any) -> HexBytes:
        signed_tx = self.w3.eth.account.sign_transaction(transaction, self.private_key)
        return await self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    async def __get_trx_params(self) -> TxParams:
        base_fee = await self.w3.eth.gas_price
        max_priority_fee_per_gas = await self.w3.eth.max_priority_fee
        max_fee_per_gas = int(base_fee + max_priority_fee_per_gas)

        trx: TxParams = {
            "from": self.address_from,
            "chainId": await self.w3.eth.chain_id,
            "nonce": await self.w3.eth.get_transaction_count(self.address_from),
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
            "maxFeePerGas": cast(Wei, max_fee_per_gas),
            "type": HexStr("0x2")
        }

        return trx

    async def get_token_balance(self, token: str) -> float:
        token = token.lower()

        print(f"Checking {token} balance...")

        if token not in dict(self.chain.get("tokens")):
            print(f"Sorry we don`t support {token}")
            return 0

        token_address: str = dict(self.chain.get("tokens")).get(token)

        token_contract: AsyncContract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=self.abi
        )

        decimals: int = await token_contract.functions.decimals().call()
        balance: int = await token_contract.functions.balanceOf(self.address_from).call()

        return balance / (10 ** decimals)

    async def send(self, *, amount: int | float, to, token: str) -> HexBytes | None:
        token = token.lower()

        if token not in dict(self.chain.get("tokens")):
            print(f"Sorry we don`t support {token}")
            return None

        print(f"Sending {amount} {token.upper()} to {to} ...")

        contract: AsyncContract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(dict(self.chain.get("tokens")).get(token)),
            abi=self.abi
        )

        decimals: int = await contract.functions.decimals().call()
        amount_wei = self.to_wei(amount=amount, decimals=decimals)

        tx_params = await self.__get_trx_params()

        transaction = await contract.functions.transfer(
            self.w3.to_checksum_address(to),
            amount_wei
        ).build_transaction(tx_params)

        return await self.__send(transaction)

    async def wait_tx(self, *, hex_bytes: HexBytes):
        total_time = 0
        timeout = 100
        poll_latency = 10
        tx_hash: str = hex_bytes.hex()

        while True:
            try:
                receipts = await self.w3.eth.get_transaction_receipt(HexStr(tx_hash))
                status = receipts.get("status")
                if status == 1:
                    print(f"Transaction was successful: {self.chain.get("explorer_url")}tx/0x{hex_bytes.hex()}")
                    return True
                elif status is None:
                    await asyncio.sleep(poll_latency)
                else:
                    print(f"Transaction failed: {self.chain.get("explorer_url")}tx/0x{hex_bytes.hex()}")
                    return False
            except TransactionNotFound:
                if total_time > timeout:
                    print(f"Transaction isn`t in the chain after {timeout} seconds")
                    return False
                total_time += poll_latency
                await asyncio.sleep(poll_latency)
