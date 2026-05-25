"""
Service Layer: lógica de negócio dos usuários.

CONCEITO — POR QUE TER UM "SERVICE"?
Em apps pequenos, é tentador colocar lógica direto na UI (Flet) ou no
modelo. Isso vira bagunça rápido. O padrão é separar:

  UI (Flet) -> Service (regras de negócio) -> Model (banco)

Vantagens:
  1. Pode testar a lógica sem subir a UI (testes mais rápidos)
  2. Pode trocar a UI (Flet -> web) sem reescrever a lógica
  3. Pode trocar o ORM (SQLAlchemy -> outro) sem mexer na UI
"""


from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.database.models import User


class UserAlreadyExistsError(Exception):
    """Lançada quando alguém tenta criar usuário com e-mail já cadastrado."""
    pass


class InvalidCredentialsError(Exception):
    """Lançada quando login falha (e-mail não existe OU senha errada).

    Repare: NÃO diferenciamos "e-mail inexistente" de "senha errada"
    nas mensagens de erro para o usuário final. Isso evita que um
    atacante descubra quais e-mails estão cadastrados (enumeration attack).
    """
    pass


def create_user(
    session: Session,
    email: str,
    password: str,
    name: str,
    is_admin: bool = False,
) -> User:
    """
    Cria um novo usuário no banco.

    Esta função recebe a `session` de fora em vez de criar uma internamente.
    Esse padrão se chama "dependency injection" e tem duas vantagens:
      1. O chamador controla a transação (pode criar várias coisas atômicas)
      2. Em testes, podemos passar uma sessão fake
    """
    # Normaliza o e-mail (tudo minúsculo, sem espaços nas pontas)
    email = email.strip().lower()

    # Verifica se já existe — usando a nova API select() do SQLAlchemy 2.x
    # (mais explícita e type-safe que a antiga session.query())
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise UserAlreadyExistsError(f"Já existe usuário com e-mail {email}")

    # Cria o objeto Python (ainda NÃO está no banco)
    user = User(
        email=email,
        password_hash=hash_password(password),  # <-- senha vira hash aqui
        name=name.strip(),
        is_admin=is_admin,
    )

    # session.add() prepara o INSERT, mas só executa no commit()
    session.add(user)
    session.commit()
    session.refresh(user)  # recarrega o objeto para pegar o ID gerado

    return user


def authenticate(session: Session, email: str, password: str) -> User:
    """
    Verifica e-mail + senha. Retorna o User se OK, lança erro se não.

    Esta função é o coração do login. A UI vai chamar:
        try:
            user = authenticate(session, email, senha)
            # ... entrar no app
        except InvalidCredentialsError:
            # ... mostrar mensagem de erro genérica
    """
    email = email.strip().lower()

    user = session.scalar(select(User).where(User.email == email))

    # IMPORTANTE: mesmo se o usuário não existir, fazemos uma comparação
    # bcrypt "falsa" para evitar timing attack (atacante medindo o tempo
    # de resposta para descobrir se o e-mail existe). O hash abaixo é
    # um bcrypt válido de uma string aleatória — qualquer hash bcrypt
    # válido serve aqui, o que importa é gastar o mesmo tempo.
    if user is None:
        verify_password(
            password,
            "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        )
        raise InvalidCredentialsError("Credenciais inválidas")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Credenciais inválidas")

    return user


