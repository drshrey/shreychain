"""
author: drshrey
purpose: gain a more intimate understanding of the technical aspects of a blockchain
"""

from time import time
import json
import hashlib
from uuid import uuid4
import requests
from urllib.parse import urlparse
import sys

from flask import Flask, jsonify, request


class Blockchain:
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.new_block(proof=1, previous_hash=100)
        self.nodes = set()

    def register_node(self, node_address):
        address = urlparse(node_address)
        self.nodes.add(address)

    def resolve_conflicts(self):
        """
        returns True if chain is replaced
        """
        max_length = len(self.chain)
        new_chain = None

        for neighbor in self.nodes:
            neighbor = neighbor.geturl()
            response = requests.get(f'{neighbor}/chain')
            if response.json().get('length') > max_length and self.valid_chain(response.json().get('chain')):
                new_chain = response.json().get('chain')
                max_length = max_length

        if new_chain:
            self.chain = new_chain
            return True

        return False



    def valid_chain(self, chain):
        """
        checks if chain is valid
        """
        previous_block = chain[0]
        index = 1
        while index < len(chain):
            block = chain[index]
            if block['previous_hash'] != self.hash(previous_block):
                return False
            if not self.valid_proof(block['proof'], previous_block['proof']):
                return False
            index += 1
            previous_block = block
        return True


    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'proof': proof,
            'transactions': self.current_transactions,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # reset current_transactions
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        transaction = {
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        }
        self.current_transactions.append(transaction)
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(proof, last_proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(proof, last_proof):
        guess = f'{proof}{last_proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:5] == "00000"

# API Config

app = Flask(__name__)
node_identifier = str(uuid4()).replace('-', '')

blockchain = Blockchain()

# API Routes

@app.route('/mine', methods=['GET'])
def mine():
    # We run the proof of work algorithm to get the next proof...
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # We must receive a reward for finding the proof.
    # The sender is "0" to signify that this node has mined a new coin.
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # Forge the new Block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    # get values
    values = request.get_json()
    print(values)

    # validate
    required = ['recipient', 'sender', 'amount']
    if not all(k in required for k in values):
        return "Input all args", 400

    # create new transaction
    new_block_index = blockchain.new_transaction(values.get('sender'),
            values.get('recipient'), values.get('amount'))
    return jsonify({ "message": f'Transaction will be added to Block {new_block_index}'}), 201

    # return created transaction

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }

    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register():
    values = request.get_json()
    required = ['nodes']
    if not all(k in required for k in values):
        return "Input all args", 400
    nodes = values.get('nodes')
    for node in nodes:
        blockchain.register_node(node)
    return jsonify({ "message": f'Nodes {nodes} added to chain.'}), 201

@app.route('/nodes/resolve', methods=['GET'])
def resolve():
   """
   - call resolve_conflicts for each neighbor node
   - if replaced, say it
   """
   replaced = blockchain.resolve_conflicts()
   if replaced:
       return jsonify({
        "message": "Chain was replaced"
       }), 200
   else:
       return jsonify({
        "message": "No need to replace. Your chain is authoritative."
       }), 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(sys.argv[1]))
