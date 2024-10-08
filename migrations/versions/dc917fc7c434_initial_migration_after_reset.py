"""Initial migration after reset

Revision ID: dc917fc7c434
Revises: 
Create Date: 2024-08-30 20:28:53.690320

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dc917fc7c434'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('forum_post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image', sa.String(length=150), nullable=True))
        batch_op.drop_column('media_url')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('forum_post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('media_url', sa.VARCHAR(length=255), nullable=True))
        batch_op.drop_column('image')

    # ### end Alembic commands ###
