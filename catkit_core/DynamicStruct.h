#ifndef DYNAMIC_STRUCT_H
#define DYNAMIC_STRUCT_H

#include <cstddef>
#include <tuple>
#include <array>
#include <map>
#include <iostream>
#include <string_view>
#include <type_traits>
#include <algorithm>

template <typename T, template <typename...> class A>
struct is_specialization_of : std::false_type {};

template <template <typename...> class A, typename... Args>
struct is_specialization_of<A<Args...>, A> : std::true_type {};

template <typename T, template <typename...> class A>
inline constexpr bool is_specialization_of_v = is_specialization_of<T, A>::value;

template<template<class> class Pred, class Sequence>
struct filter;

template<bool>
struct zero_or_one {
    template<class E> using type = std::tuple<E>;
};

template<>
struct zero_or_one<false> {
    template<class E> using type = std::tuple<>;
};

template<template<class> class Pred, class... Es>
struct filter<Pred, std::tuple<Es...>> {
    using type = decltype(std::tuple_cat(std::declval<typename zero_or_one<Pred<Es>::value>::template type<Es>>()...));
};

// Compile-time string wrapper
// TODO: use std::string_view instead.
template <size_t N>
struct FixedString {
	char value[N];

	constexpr FixedString(const char (&str)[N]) {
		std::copy_n(str, N, value);
	}

	constexpr bool operator==(const FixedString& other) const {
		return std::equal(value, value + N, other.value);
	}

	constexpr operator char const*() const
	{
		return value;
	}

	constexpr operator std::string_view() const
	{
		return std::string_view(value, N - 1);
	}
};

// Deduction guide for FixedString.
template<size_t N>
FixedString(const char (&)[N]) -> FixedString<N>;

constexpr const size_t Dynamic = 0;

// Pre-declaration of StructSpec.
template <typename... Fields>
struct StructSpec;

// NamedField definition.
template <FixedString Name, typename T, size_t NumElements = 1>
struct NamedField
{
private:
	static constexpr size_t _GetAlignment()
	{
		if constexpr (is_struct)
		{
			return std::tuple_element_t<0, typename T::FieldsTuple>::alignment;
		}
		else
		{
			return alignof(T);
		}
	}

public:
	using type = T;

	static constexpr FixedString name = Name;
	static constexpr size_t num_elements = NumElements;
	static constexpr bool is_dynamic = NumElements == Dynamic;
	static constexpr bool is_struct = is_specialization_of_v<T, StructSpec>;
	static constexpr size_t alignment = _GetAlignment();
};

struct NumElementsSpec
{
	std::string name;
	size_t num_elements;
	std::vector<NumElementsSpec> recursive_spec;

	NumElementsSpec(std::string name, std::size_t num_elements, std::vector<NumElementsSpec> recursive_spec = {})
		: name(name), num_elements(num_elements), recursive_spec(recursive_spec)
	{
	}

	NumElementsSpec &operator[](std::string_view key)
	{
		// Linear search. This is fine since this is done once during initialization.
		for (auto &spec : recursive_spec)
		{
			if (spec.name == key)
				return spec;
		}

		throw std::runtime_error("Key not found!");
	}
};

template <typename T>
struct is_dynamic
{
	static constexpr bool value = T::is_dynamic;
};

template <typename T>
struct is_static : public std::negation<is_dynamic<T>>
{
};

template <typename T>
struct is_struct
{
	static constexpr bool value = T::is_struct;
};

template <typename Tuple, template <typename> class UnaryFunction, std::size_t... I>
constexpr auto tuple_types_to_array_helper(std::index_sequence<I...>)
{
	return std::array{UnaryFunction<std::tuple_element_t<I, Tuple>>::value...};
}

template <typename Tuple, template <typename> class UnaryFunction>
constexpr auto tuple_types_to_array()
{
	return tuple_types_to_array_helper<Tuple, UnaryFunction>(std::make_index_sequence<std::tuple_size_v<Tuple>>{});
}

template <typename Tuple, template <typename> typename Transform>
struct transform_tuple_to_array;

template <typename... Ts, template <typename> typename Transform>
struct transform_tuple_to_array<std::tuple<Ts...>, Transform>
{
	static constexpr auto value = std::array{Transform<Ts>::value ...};
};

template <typename Tuple, template <typename> typename Transform>
struct transform_tuple;

template <typename... Ts, template <typename> typename Transform>
struct transform_tuple<std::tuple<Ts...>, Transform>
{
	using type = std::tuple<typename Transform<Ts>::type ...>;
};

template <typename Field>
struct get_field_name
{
	static constexpr std::string_view value = Field::name;
};

template <typename Field>
struct get_field_type
{
	using type = typename Field::type;
};

template <typename... Fields>
class StructSpec;

template <typename Tuple, std::size_t... Is>
typename transform_tuple<Tuple, get_field_type>::type construct_substructs_tuple_helper(NumElementsSpec &spec, std::index_sequence<Is...>)
{
	return {spec[std::tuple_element_t<Is, Tuple>::name] ...};
}

template <typename Tuple>
auto construct_substructs_tuple(NumElementsSpec &spec)
{
	return construct_substructs_tuple_helper<Tuple>(spec, std::make_index_sequence<std::tuple_size_v<Tuple>>{});
}

// The specifications for a struct.
template <typename... Fields>
class StructSpec
{
	template <typename...>
	friend struct StructSpec;

public:
	static constexpr size_t NumFields = sizeof...(Fields);
	static constexpr size_t NumDynamicFields = (0 + ... + Fields::is_dynamic);
	static constexpr size_t NumStaticFields = (0 + ... + !Fields::is_dynamic);
	static constexpr size_t NumStructFields = (0 + ... + Fields::is_struct);

	using FieldsTuple = std::tuple<Fields...>;
	using DynamicFieldsTuple = typename filter<is_dynamic, FieldsTuple>::type;
	using StaticFieldsTuple = typename filter<is_static, FieldsTuple>::type;
	using StructFieldsTuple = typename filter<is_struct, FieldsTuple>::type;
	using StructSpecsTuple = typename transform_tuple<StructFieldsTuple, get_field_type>::type;

	static constexpr std::array<std::string_view, NumFields> FieldNames{(const char *) Fields::name...};
	static constexpr std::array<std::string_view, NumStructFields> StructFieldNames = transform_tuple_to_array<StructFieldsTuple, get_field_name>::value;

	StructSpec(NumElementsSpec spec)
		: m_StructFields{construct_substructs_tuple<StructFieldsTuple>(spec)}
	{
		ComputeOffsets(spec);
	}

	StructSpec(std::initializer_list<NumElementsSpec> spec)
		: StructSpec(NumElementsSpec("root", 1, spec))
	{
	}

	StructSpec(const StructSpec &other)
		: m_Offsets(other.m_Offsets),
		m_NumElements(other.m_NumElements),
		m_ElementSize(other.m_ElementSize),
		m_TotalSize(other.m_TotalSize),
		m_StructFields(other.m_StructFields)
	{
	}

	template <FixedString Name>
	size_t GetOffset()
	{
		constexpr size_t index = GetFieldIndex(Name);
		static_assert(index < NumFields, "Field name not found!");

		return m_Offsets[index];
	}

	template <FixedString Name>
	auto GetSubSpec()
	{
		constexpr size_t index = GetStructFieldIndex(Name);
		static_assert(index < NumStructFields, "Field name not found!");

		return std::get<index>(m_StructFields);
	}

	static StructSpec Build(std::initializer_list<NumElementsSpec> num_elements_spec)
	{
		return StructSpec(NumElementsSpec("root", 1, num_elements_spec));
	}

	size_t GetSize() const
	{
		return m_TotalSize;
	}

	void Print()
	{
		std::cout << "Total size: " << m_TotalSize << std::endl;

		std::cout << "Fields:" << std::endl;
		for (size_t i = 0; i < NumFields; ++i)
		{
			std::cout << FieldNames[i] << ": " << std::endl;
			std::cout << "  Offset: " << m_Offsets[i] << std::endl;
			std::cout << "  NumElements: " << m_NumElements[i] << std::endl;
			std::cout << "  ElementSize: " << m_ElementSize[i] << std::endl;
		}
	}

private:
	// Offsets and sizes for dynamic fields.
	std::array<size_t, NumFields> m_Offsets;
	std::array<size_t, NumFields> m_NumElements;
	std::array<size_t, NumFields> m_ElementSize;

	StructSpecsTuple m_StructFields;

	std::size_t m_TotalSize;

	// Compile-time field index lookup.
	static constexpr size_t GetFieldIndex(std::string_view name)
	{
		for (size_t i = 0; i < NumFields; ++i)
		{
			if (FieldNames[i] == name)
				return i;
		}

		return NumFields;
	}

	static constexpr size_t GetStructFieldIndex(std::string_view name)
	{
		for (size_t i = 0; i < NumStructFields; ++i)
		{
			if (StructFieldNames[i] == name)
				return i;
		}

		return NumStructFields;
	}

	void ComputeOffsets(NumElementsSpec spec)
	{
		size_t offset = 0;
		// TODO: removed index incrementing.

		// Compute offsets for fixed fields with respect to their alignment
		(..., (ComputeFieldOffset<Fields>(offset, spec)));

		// Compute total size, correcting for alignment of the first field.
		using FirstField = std::tuple_element_t<0, FieldsTuple>;
		constexpr size_t align = alignof(typename FirstField::type);
		size_t padding = (align - (offset % align)) % align;

		m_TotalSize = offset + padding;
	}

	// Helper function to compute the offset for fields.
	template <typename Field>
	void ComputeFieldOffset(size_t& offset, NumElementsSpec spec)
	{
		constexpr std::size_t index = GetFieldIndex(Field::name);
		static_assert(index < NumFields, "Field name not found!");

		// Compute and add the padding for the field.
		constexpr size_t align = Field::alignment;
		size_t padding = (align - (offset % align)) % align;

		offset += padding;
		m_Offsets[index] = offset;

		// Get the number of elements of the field.
		m_NumElements[index] = Field::is_dynamic ? spec[Field::name].num_elements : Field::num_elements;

		// Set the size of each element in the field.
		if constexpr (Field::is_struct)
		{
			constexpr size_t struct_index = GetStructFieldIndex(Field::name);
			static_assert(struct_index < NumStructFields, "Field name not found!");

			m_ElementSize[index] = std::get<struct_index>(m_StructFields).GetSize();
		}
		else
		{
			m_ElementSize[index] = sizeof(typename Field::type);
		}

		// Update the offset.
		offset += m_ElementSize[index] * m_NumElements[index];
	}
};

template<typename StructSpec>
class Struct
{
public:
	Struct(void *buffer, StructSpec spec)
		: m_Buffer(buffer), m_Spec(spec)
	{
	}

	template<FixedString Name>
	void *Get()
	{
		return nullptr;
	}

private:
	void *m_Buffer;
	StructSpec m_Spec;
};

// USAGE:

void usage()
{
	using NestedStructSpec = StructSpec<
		NamedField<"e", int>,
		NamedField<"f", double, Dynamic>>;

	using MyStructSpec = StructSpec<
		NamedField<"a", int>,
		NamedField<"b", double, Dynamic>,
		NamedField<"c", char, 64>,
		NamedField<"d", NestedStructSpec, Dynamic>>;

	auto spec = MyStructSpec::Build({
		{"b", 10},
		{"d", 5, {
			{"f", 2}
			}}
		});

	spec.Print();

	void *buffer = malloc(spec.GetSize());
	Struct s = Struct(buffer, spec);

	//s.Get<"a">() = 10;
	//s.Get<"b">()[5] = 3.14;
	//s.Get<"d">()[3].Get<"e">() = 5;

	free(buffer);
}

#endif // DYNAMIC_STRUCT_H
