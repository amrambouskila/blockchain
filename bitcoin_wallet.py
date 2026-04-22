from __future__ import annotations

import hashlib
import json
import os
import random
import secrets
from decimal import Decimal

import base58
import ecdsa
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException


# Define a class BitcoinWallet for managing Bitcoin wallet operations
class BitcoinWallet:
    def __init__(
        self,
        rpc_credentials_file: str = 'rpc_credentials.json',
        private_key: str | None = None,
    ) -> None:
        # Initialize the wallet with an optional private key
        self.rpc_credentials = self.get_rpc_credentials(rpc_credentials_file)
        self.rpc_connection = self.connect_to_rpc()

        if private_key is None:
            # If no private key is provided, generate a new one
            self.private_key = self.generate_private_key()
        else:
            # Use the provided private key
            self.private_key = private_key

        # Derive the public key from the private key
        self.public_key = self.derive_public_key(self.private_key)
        # Generate a Bitcoin address from the public key
        self.address = self.generate_address(self.public_key)

    @staticmethod
    def get_rpc_credentials(file_path: str) -> dict[str, str]:
        if os.path.exists(file_path):
            # Load existing credentials if the file exists
            with open(file_path) as file:
                credentials = json.load(file)
        else:
            # Generate new RPC credentials
            credentials = {
                "rpc_user": "user_" + secrets.token_hex(4),
                "rpc_password": secrets.token_hex(16)
            }
            # Save the credentials to the JSON file
            with open(file_path, 'w') as file:
                json.dump(credentials, file)

        return credentials

    def connect_to_rpc(self) -> AuthServiceProxy:
        rpc_user = self.rpc_credentials['rpc_user']
        rpc_password = self.rpc_credentials['rpc_password']
        rpc_url = f'http://{rpc_user}:{rpc_password}@127.0.0.1:8332'
        return AuthServiceProxy(rpc_url)

    @staticmethod
    def generate_private_key() -> str:
        # Securely generate a random 256-bit private key using secrets and os for high entropy
        entropy = secrets.token_bytes(32) + os.urandom(32) + random.getrandbits(256).to_bytes(32, 'big')
        return hashlib.sha256(entropy).hexdigest()

    @staticmethod
    def derive_public_key(private_key_hex: str) -> str:
        # Derive an ECDSA public key from the provided hex-encoded private key
        private_key_bytes = bytes.fromhex(private_key_hex)
        signing_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
        verifying_key = signing_key.get_verifying_key()

        # Get the x and y coordinates of the public key
        public_key_point = verifying_key.pubkey.point
        x = public_key_point.x()
        y = public_key_point.y()

        # Convert x coordinate to bytes
        x_bytes = x.to_bytes(32, 'big')

        # Determine if y is even or odd, and prepend 0x02 or 0x03 accordingly
        if y % 2 == 0:
            prefix = b'\x02'
        else:
            prefix = b'\x03'

        compressed_public_key_bytes = prefix + x_bytes

        # Return the compressed public key as a hex string
        return compressed_public_key_bytes.hex()

    @staticmethod
    def generate_address(public_key_hex: str) -> str:
        # Generate a Bitcoin address from a hex-encoded public key
        public_key_bytes = bytes.fromhex(public_key_hex)
        sha256_pubkey = hashlib.sha256(public_key_bytes).digest()
        ripemd160 = hashlib.new('ripemd160', sha256_pubkey).digest()
        network_byte = b'\x00' + ripemd160  # For mainnet addresses
        checksum = hashlib.sha256(hashlib.sha256(network_byte).digest()).digest()[:4]
        binary_address = network_byte + checksum
        address = base58.b58encode(binary_address)
        return address.decode()

    def get_balance(self) -> Decimal | int:
        # Retrieve UTXOs for the wallet address to calculate the balance
        try:
            utxos = self.rpc_connection.listunspent(0, 9999999, [self.address])
            balance = sum(utxo['amount'] for utxo in utxos)
            return balance
        except JSONRPCException as e:
            print(f"An error occurred: {e}")
            return 0

    def create_raw_transaction(
        self,
        inputs: list[dict[str, object]],
        outputs: dict[str, Decimal | float],
    ) -> str | None:
        # Create a raw transaction using the inputs and outputs
        try:
            raw_tx = self.rpc_connection.createrawtransaction(inputs, outputs)
            return raw_tx
        except JSONRPCException as e:
            print(f"An error occurred while creating raw transaction: {e}")
            return None

    def sign_transaction(self, raw_tx: str) -> str | None:
        # Sign the raw transaction using the wallet's private key
        try:
            signed_tx = self.rpc_connection.signrawtransactionwithkey(raw_tx, [self.private_key])
            return signed_tx['hex']
        except JSONRPCException as e:
            print(f"An error occurred while signing the transaction: {e}")
            return None

    def broadcast_transaction(self, signed_tx: str) -> str | None:
        # Broadcast the signed transaction to the Bitcoin network
        try:
            tx_id = self.rpc_connection.sendrawtransaction(signed_tx)
            return tx_id
        except JSONRPCException as e:
            print(f"An error occurred while broadcasting the transaction: {e}")
            return None

    def create_and_send_transaction(self, recipient_address: str, amount: float) -> None:
        # Create and send a transaction
        utxos = self.rpc_connection.listunspent(0, 9999999, [self.address])
        total_input = 0
        inputs = []

        for utxo in utxos:
            inputs.append({"txid": utxo['txid'], "vout": utxo['vout']})
            total_input += utxo['amount']
            if total_input >= amount:
                break

        if total_input < amount:
            raise ValueError("Insufficient funds for the transaction.")

        change_amount = total_input - amount - 0.0001  # Subtract fee
        outputs = {
            recipient_address: amount
        }

        if change_amount > 0:
            outputs[self.address] = change_amount

        raw_tx = self.create_raw_transaction(inputs, outputs)
        if raw_tx:
            signed_tx = self.sign_transaction(raw_tx)
            if signed_tx:
                tx_id = self.broadcast_transaction(signed_tx)
                if tx_id:
                    print(f"Transaction broadcasted successfully! TXID: {tx_id}")
                else:
                    print("Failed to broadcast transaction.")
            else:
                print("Failed to sign transaction.")
        else:
            print("Failed to create raw transaction.")


# Main execution block to run the script as a standalone module
if __name__ == '__main__':
    wallet = BitcoinWallet()  # Instantiate a BitcoinWallet
    balance = wallet.get_balance()
    print(f"Wallet Address: {wallet.address}")
    print(f"Wallet Balance: {balance} BTC")

    recipient_address = 'recipient_btc_address_here'  # Define recipient's Bitcoin address
    amount = 0.009  # Set the amount to be sent in BTC

    try:
        wallet.create_and_send_transaction(recipient_address, amount)
    except ValueError as e:
        print(f"Error: {e}")
