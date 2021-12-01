from collections import defaultdict
from contextlib import contextmanager

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

class OpticalModel:
    def __init__(self):
        self._plane_dependencies = {}
        self._plane_dependents = defaultdict(list)
        self._plane_propagators = {}

        self.purge_all()

    def purge_all(self):
        self._cached_wavefronts = defaultdict(lambda: None)

    def purge_plane(self, plane_name):
        self._cached_wavefronts[plane_name] = None

        for dep in self._plane_dependents[plane_name]:
            self.purge_plane(dep)

    @contextmanager
    def _temperary_cache(self, new_cache=None):
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
        in_cache = self._cached_wavefronts[plane]

        if in_cache is not None:
            return in_cache

        prop = self._plane_propagators[plane]
        dependencies = self._plane_dependencies[plane]

        input_wavefronts = []
        for dep in dependencies:
            input_wavefronts.append(self.get_wavefronts(dep))

        output_wavefronts = []
        for args in zip(*input_wavefronts):
            output_wavefronts.append(prop(*args))

        self._cached_wavefronts[plane] = output_wavefronts
        return output_wavefronts
