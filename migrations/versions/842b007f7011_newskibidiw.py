"""newskibidiw

Revision ID: 842b007f7011
Revises: 2840a27a6f47
Create Date: 2025-03-01 16:50:20.275303

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '842b007f7011'
down_revision = '2840a27a6f47'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('email_verified', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('password_reset_token', sa.String(length=100), nullable=True))
    op.add_column('user', sa.Column('token_expiration', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'token_expiration')
    op.drop_column('user', 'password_reset_token')
    op.drop_column('user', 'email_verified')
    # ### end Alembic commands ###
