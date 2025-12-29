# -*- coding: utf-8 -*-
"""
Alembic environment configuration for SAGL migrations
"""
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
src_dir = project_root / 'src'
sys.path.insert(0, str(src_dir))

from openlegis.sagl.models.alembic_env import *
