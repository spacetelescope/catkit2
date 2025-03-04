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

// Compile-time string wrapper
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

// Pre-declaration of DynamicStruct.
template <typename... Fields>
struct DynamicStruct;

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
	static constexpr bool is_struct = is_specialization_of_v<T, DynamicStruct>;
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
		for (auto &spec : recursive_spec)
		{
			if (spec.name == key)
				return spec;
		}

		throw std::runtime_error("Key not found!");
	}
};

// Helper function to explicitly call the destructor.
template <typename T>
void destroy(T* obj)
{
	obj->~T();
}

// DynamicStruct that stores both fixed and dynamic fields in the same buffer.
template <typename... Fields>
struct DynamicStruct
{
	static constexpr size_t NumFields = sizeof...(Fields);
	static constexpr size_t NumDynamicFields = (0 + ... + Fields::is_dynamic);

	static constexpr std::array<std::string_view, NumFields> FieldNames{(const char *) Fields::name...};

	using FieldsTuple = std::tuple<Fields...>;

	void* m_Buffer;

	// Offsets and sizes for dynamic fields.
	std::array<size_t, NumFields> m_Offsets;
	std::array<size_t, NumFields> m_NumElements;
	std::array<size_t, NumFields> m_ElementSize;
	std::array<void *, NumFields> m_Fields;

	std::size_t m_TotalSize;
	bool m_Owner;

	DynamicStruct(void* buffer, std::vector<NumElementsSpec> spec)
		: m_Buffer(buffer), m_Owner(true)
	{
		ComputeOffsets(NumElementsSpec("root", 1, spec));
	}

	DynamicStruct(const DynamicStruct &other)
		: m_Buffer(other.m_Buffer),
		m_Offsets(other.m_Offsets),
		m_NumElements(other.m_NumElements),
		m_ElementSize(other.m_ElementSize),
		m_TotalSize(other.m_TotalSize),
		m_Owner(false)
	{
	}

	~DynamicStruct()
	{
		if (!m_Owner)
			return;

		(..., (DeleteField<Fields>()));
	}

	// Accessor for fields.
	template <FixedString Name>
	auto *Get()
	{
		constexpr size_t index = GetFieldIndex(Name);
		static_assert(index < NumFields, "Field name not found!");

		return reinterpret_cast<typename std::tuple_element_t<index, FieldsTuple>::type *>(m_Fields[index]);
	}

private:
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

	template<typename Field>
	static constexpr size_t GetFieldAlignment()
	{
		if constexpr (Field::is_struct)
		{
			return Field::type::Alignments[0];
		}
		else
		{
			return alignof(typename Field::type);
		}
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

		// Create the field.
		char *memory = static_cast<char*>(m_Buffer) + offset;
		if constexpr (Field::is_struct)
		{
			// Create the field using the dynamic struct.
			m_Fields[index] = new typename Field::type(memory, spec[Field::name].recursive_spec);
		}
		else
		{
			// Create the field using placement new.
			m_Fields[index] = new (memory) typename Field::type();
		}

		// Get the number of elements of the field.
		m_NumElements[index] = Field::is_dynamic ? spec[Field::name].num_elements : Field::num_elements;

		// Get the size of each element in the field.
		if constexpr (Field::is_struct)
		{
			m_ElementSize[index] = reinterpret_cast<Field::type *>(m_Fields[index])->m_TotalSize;
		}
		else
		{
			m_ElementSize[index] = sizeof(typename Field::type);
		}

		// Update the offset.
		offset += m_ElementSize[index] * m_NumElements[index];
	}

	template<typename Field>
	void DeleteField()
	{
		constexpr size_t index = GetFieldIndex(Field::name);
		static_assert(index < NumFields, "Field name not found!");

		if constexpr (Field::is_struct)
		{
			// Field was created using new, so delete it.
			delete reinterpret_cast<typename Field::type *>(m_Fields[index]);
		}
		else
		{
			// Field was created using placement new, so call the destructor.
			destroy(reinterpret_cast<typename Field::type *>(m_Fields[index]));
		}
	}
};

#endif // DYNAMIC_STRUCT_H
