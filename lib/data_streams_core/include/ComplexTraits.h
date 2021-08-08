#ifndef COMPLEXTRAITS_H
#define COMPLEXTRAITS_H

#include <complex>
#include <type_traits>

template<class T> struct is_complex : std::false_type {};
template<class T> struct is_complex<std::complex<T>> : std::true_type {};

#endif // COMPLEXTRAITS_H
