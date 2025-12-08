
# Namespace package declaration
# This allows Products subpackages in different locations to be found
import os
import sys

def _add_products_paths_to_namespace():
    """Add all Products paths (src and eggs) to Products namespace"""
    paths_to_add = []
    
    # 1. Add src/Products
    current_dir = os.path.dirname(__file__)  # Products.CMFDefault/Products
    parent_dir = os.path.dirname(current_dir)  # Products.CMFDefault
    grandparent_dir = os.path.dirname(parent_dir)  # src
    src_products_path = os.path.join(grandparent_dir, 'Products')
    if os.path.exists(src_products_path):
        paths_to_add.append(src_products_path)
    
    # 2. Add Products paths from eggs in sys.path
    for path in sys.path:
        if 'egg' in path.lower() or path.endswith('.egg'):
            products_in_egg = os.path.join(path, 'Products')
            if os.path.exists(products_in_egg) and products_in_egg not in paths_to_add:
                paths_to_add.append(products_in_egg)
    
    if not paths_to_add:
        return
    
    # Use a module finder hook to add paths when Products is imported
    class ProductsNamespaceFinder:
        def __init__(self, paths):
            self.paths = paths
        
        def find_spec(self, name, path, target=None):
            if name == 'Products' and 'Products' in sys.modules:
                Products = sys.modules['Products']
                if hasattr(Products, '__path__'):
                    current_paths = list(Products.__path__) if hasattr(Products.__path__, '__iter__') else []
                    for p in self.paths:
                        if p not in current_paths:
                            current_paths.append(p)
                    Products.__path__ = current_paths
            return None
    
    # Add finder if not already added
    finder = ProductsNamespaceFinder(paths_to_add)
    if not any(isinstance(f, ProductsNamespaceFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, finder)
    
    # Also try to add immediately if Products is already imported
    if 'Products' in sys.modules:
        Products = sys.modules['Products']
        if hasattr(Products, '__path__'):
            current_paths = list(Products.__path__) if hasattr(Products.__path__, '__iter__') else []
            for p in paths_to_add:
                if p not in current_paths:
                    current_paths.append(p)
            Products.__path__ = current_paths

try:
    import pkg_resources
    pkg_resources.declare_namespace(__name__)
    _add_products_paths_to_namespace()
except ImportError:
    # Fallback for systems without pkg_resources
    _add_products_paths_to_namespace()
