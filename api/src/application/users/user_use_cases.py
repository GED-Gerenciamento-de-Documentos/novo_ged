"""Application Use Cases — User authentication and management."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

import structlog
from passlib.context import CryptContext

from src.domain.audit.entities.audit_log import AuditAction, AuditLog
from src.domain.audit.repositories.audit_repository import IAuditRepository
from src.domain.users.entities.user import User, UserRole
from src.domain.users.repositories.user_repository import IUserRepository
from src.infrastructure.cache.redis_cache import RedisCache
from src.infrastructure.security.jwt_service import JwtService

logger = structlog.get_logger()

# Bcrypt para hashing de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_LOGIN_ATTEMPTS = 5  # Bloquear após 5 tentativas falhas


# ==========================================
# Authenticate User Use Case
# ==========================================

@dataclass
class AuthenticateInput:
    email: str
    password: str
    ip_address: str
    user_agent: str


@dataclass
class AuthenticateOutput:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int = 60


class AuthenticateUserUseCase:
    """Autentica usuário e emite JWT + refresh token."""

    def __init__(
        self,
        user_repository: IUserRepository,
        audit_repository: IAuditRepository,
    ):
        self._user_repository = user_repository
        self._audit_repository = audit_repository

    async def execute(self, input_data: AuthenticateInput) -> AuthenticateOutput:
        # 1. Verificar rate limit de tentativas
        attempts = await RedisCache.get_login_attempts(input_data.email)
        if attempts >= MAX_LOGIN_ATTEMPTS:
            logger.warning("login_blocked", email=input_data.email, attempts=attempts)
            raise PermissionError(
                "Conta temporariamente bloqueada por excesso de tentativas. "
                "Tente novamente em 15 minutos."
            )

        # 2. Buscar usuário
        user = await self._user_repository.find_by_email(input_data.email)

        # 3. Verificar credenciais
        if not user or not user.is_active or not pwd_context.verify(
            input_data.password, user.password_hash
        ):
            await RedisCache.increment_login_attempts(input_data.email)
            await self._audit_repository.save(
                AuditLog.create(
                    action=AuditAction.FAILED_LOGIN,
                    user_id=user.id if user else uuid.uuid4(),
                    user_email=input_data.email,
                    user_role=user.role.value if user else "UNKNOWN",
                    ip_address=input_data.ip_address,
                    user_agent=input_data.user_agent,
                    success=False,
                    error_message="Credenciais inválidas",
                )
            )
            raise ValueError("E-mail ou senha inválidos.")

        # 4. Login bem-sucedido — resetar contador e registrar
        await RedisCache.reset_login_attempts(input_data.email)
        user.record_login()
        await self._user_repository.update(user)

        # 5. Gerar tokens JWT
        access_token = JwtService.create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role.value,
        )
        refresh_token = JwtService.create_refresh_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role.value,
        )

        # 6. Audit log de login
        await self._audit_repository.save(
            AuditLog.create(
                action=AuditAction.LOGIN,
                user_id=user.id,
                user_email=user.email,
                user_role=user.role.value,
                ip_address=input_data.ip_address,
                user_agent=input_data.user_agent,
            )
        )

        logger.info("user_login_success", email=user.email, role=user.role.value)

        from src.settings import get_settings
        settings = get_settings()
        return AuthenticateOutput(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        )


# ==========================================
# Create User Use Case
# ==========================================

@dataclass
class CreateUserInput:
    name: str
    email: str
    password: str
    role: UserRole
    department: str
    created_by_role: str


class CreateUserUseCase:
    """Cria novo usuário. Apenas ADMINISTRADOR pode criar."""

    def __init__(self, user_repository: IUserRepository):
        self._user_repository = user_repository

    async def execute(self, input_data: CreateUserInput) -> User:
        if input_data.created_by_role != "ADMINISTRADOR":
            raise PermissionError("Somente ADMINISTRADOR pode criar usuários.")

        if await self._user_repository.exists_by_email(input_data.email):
            raise ValueError(f"Já existe um usuário com o e-mail: {input_data.email}")

        password_hash = pwd_context.hash(input_data.password)

        user = User.create_new(
            name=input_data.name,
            email=input_data.email,
            password_hash=password_hash,
            role=input_data.role,
            department=input_data.department,
        )

        saved_user = await self._user_repository.save(user)
        logger.info("user_created", email=input_data.email, role=input_data.role.value)
        return saved_user
