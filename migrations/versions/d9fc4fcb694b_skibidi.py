"""skibidi

Revision ID: d9fc4fcb694b
Revises: 6a32e95b144f
Create Date: 2025-02-15 22:07:38.996387

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9fc4fcb694b'
down_revision = '6a32e95b144f'
branch_labels = None
depends_on = None


def upgrade():
    # Use batch mode for SQLite
    #with op.batch_alter_table('comment', schema=None) as batch_op:
        #batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        pass

def downgrade():
    # Remove the column using batch mode for SQLite
    #with op.batch_alter_table('comment', schema=None) as batch_op:
        #batch_op.drop_column('parent_id')
        pass
