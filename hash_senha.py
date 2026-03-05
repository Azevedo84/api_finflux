import bcrypt

senha = input("Digite a senha que quer transformar em hash: ")

# Gerar hash
hash_senha = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())

print("\nHASH GERADO:\n")
print(hash_senha.decode())