#ifndef FINALLY_H
#define FINALLY_H

#include <functional>

class Finally
{
public:
	inline Finally(std::function<void()> func)
		: m_Func(func)
	{
	}

	inline ~Finally()
	{
		m_Func();
	}

private:
	std::function<void()> m_Func;
};

#endif // FINALLY_H
