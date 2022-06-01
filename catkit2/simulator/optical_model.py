from collections import defaultdict
from contextlib import contextmanager

import networkx as nx
import pydot
from networkx.drawing.nx_pydot import graphviz_layout

import random

def hierarchy_pos(G, root=None, width=1., vert_gap = 0.2, vert_loc = 0, xcenter = 0.5):

    '''
    From Joel's answer at https://stackoverflow.com/a/29597209/2966723.
    Licensed under Creative Commons Attribution-Share Alike

    If the graph is a tree this will return the positions to plot this in a
    hierarchical layout.

    G: the graph (must be a tree)

    root: the root node of current branch
    - if the tree is directed and this is not given,
      the root will be found and used
    - if the tree is directed and this is given, then
      the positions will be just for the descendants of this node.
    - if the tree is undirected and not given,
      then a random choice will be used.

    width: horizontal space allocated for this branch - avoids overlap with other branches

    vert_gap: gap between levels of hierarchy

    vert_loc: vertical location of root

    xcenter: horizontal location of root
    '''
    if not nx.is_tree(G):
        raise TypeError('cannot use hierarchy_pos on a graph that is not a tree')

    if root is None:
        if isinstance(G, nx.DiGraph):
            root = next(iter(nx.topological_sort(G)))  #allows back compatibility with nx version 1.11
        else:
            root = random.choice(list(G.nodes))

    def _hierarchy_pos(G, root, width=1., vert_gap = 0.2, vert_loc = 0, xcenter = 0.5, pos = None, parent = None):
        '''
        see hierarchy_pos docstring for most arguments

        pos: a dict saying where all nodes go if they have been assigned
        parent: parent of this branch. - only affects it if non-directed

        '''

        if pos is None:
            pos = {root:(xcenter,vert_loc)}
        else:
            pos[root] = (xcenter, vert_loc)
        children = list(G.neighbors(root))
        if not isinstance(G, nx.DiGraph) and parent is not None:
            children.remove(parent)
        if len(children)!=0:
            dx = width/len(children)
            nextx = xcenter - width/2 - dx/2
            for child in children:
                nextx += dx
                pos = _hierarchy_pos(G,child, width = dx, vert_gap = vert_gap,
                                    vert_loc = vert_loc-vert_gap, xcenter=nextx,
                                    pos=pos, parent = root)
        return pos


    return _hierarchy_pos(G, root, width, vert_gap, vert_loc, xcenter)

def with_cached_result(getter):
    def new_getter(self):
        try:
            res = getattr(self, '_' + getter.__name__)
        except AttributeError:
            res = None

        if res is None:
            res = getter(self)
            setattr(self, '_' + getter.__name__, res)

        return res
    return new_getter

def property_with_logic(logic_func):
    def getter(self):
        return getattr(self, '_' + logic_func.__name__)

    def setter(self, value):
        setattr(self, '_' + logic_func.__name__, value)
        logic_func(self)

    return property(getter, setter)

class OpticalModel:
    def __init__(self):
        self._plane_dependencies = {}
        self._plane_dependents = defaultdict(list)
        self._plane_propagators = {}

        self.graph = nx.DiGraph()

        self.purge_all()

    def plot_graph(self):
        options = {
            'node_color': 'green',
            'node_size': 500,
            'width': 3,
            'arrowstyle': '-|>',
            'arrowsize': 12,
        }

        #pos = nx.spring_layout(self.graph)
        #pos = graphviz_layout(self.graph, prog='dot')
        pos = hierarchy_pos(self.graph)

        nx.draw_networkx(self.graph, arrows=True, pos=pos, **options)

    def purge_all(self):
        self._cached_wavefronts = defaultdict(lambda: None)

    def purge_plane(self, plane_name):
        self._cached_wavefronts[plane_name] = None

        for dep in self._plane_dependents[plane_name]:
            self.purge_plane(dep)

    @contextmanager
    def _temporary_cache(self, new_cache=None):
        if new_cache is None:
            new_cache = defaultdict(lambda: None)

        old_cache = self._cached_wavefronts
        self._cached_wavefronts = new_cache

        try:
            yield
        finally:
            self._cached_wavefronts = old_cache

    def register_plane(self, plane, dependencies):
        if isinstance(dependencies, str):
            dependencies = [dependencies]

        self._plane_dependencies[plane] = dependencies

        for dep in dependencies:
            self._plane_dependents[dep].append(plane)

        def decorator(func):
            self._plane_propagators[plane] = func
            return func

        for dependency in dependencies:
            self.graph.add_edge(dependency, plane)

        return decorator

    def propagate(self, input_plane, output_plane, wavefronts):
        with self._temperary_cache():
            self.set_wavefronts(input_plane, wavefronts)

            res = self.get_wavefronts(output_plane)

            if len(res) == 1:
                return res[0]
            else:
                return res

    def set_wavefronts(self, plane, wavefronts):
        if not isinstance(wavefronts, list):
            wavefronts = [wavefronts]

        self.purge_plane(plane)
        self._cached_wavefronts[plane] = wavefronts

    def get_wavefronts(self, plane):
        # Try to get the wavefronts from the cache.
        in_cache = self._cached_wavefronts[plane]

        # If they are in the cache, return them.
        if in_cache is not None:
            return in_cache

        # Otherwise, we do the propagation ourselves.
        # Get the propagator and dependencies.
        prop = self._plane_propagators[plane]
        dependencies = self._plane_dependencies[plane]

        # Get the dependencies recursively.
        input_wavefronts = []
        for dep in dependencies:
            input_wavefronts.append(self.get_wavefronts(dep))

        # Compute the propagation, one wavefront at a time.
        output_wavefronts = []
        for args in zip(*input_wavefronts):
            output_wavefronts.append(prop(*args))

        # Store the computed wavefronts in the cache and return them.
        self._cached_wavefronts[plane] = output_wavefronts
        return output_wavefronts
