# MyLang Beginner Guide

Welcome to MyLang — a simple, clean scripting language designed to feel approachable from the first line you write.

This guide covers everything you need to go from zero to writing real programs.

---

## Running Your First Program

Save this as `hello.my` and run it with `python main.py hello.my`:

```
print "Hello, World!"
```

That's it. No imports, no boilerplate, no entry point function. Just write what you want to happen.

---

## Printing Output

Use `print` followed by anything:

```
print "Hello"
print 42
print true
```

You can print expressions too:

```
print 10 + 5
print "Score: " + to_str(100)
```

---

## Variables

Assign with `=`. No `var`, `let`, or `const` needed:

```
name  = "Alice"
score = 100
alive = true
```

Use them anywhere after they're assigned:

```
name = "Jeremy"
print name
```

---

## Numbers and Math

MyLang works with integers. All the standard operators work:

```
x = 10
y = 3

print x + y    # 13
print x - y    # 7
print x * y    # 30
print x / y    # 3  (integer division)
print x % y    # 1  (remainder)
```

Negative numbers work as you'd expect:

```
temp = -5
print abs(temp)   # 5
```

---

## Strings

Strings go in double quotes. Concatenate with `+`:

```
first = "Hello"
second = "World"
print first + ", " + second + "!"
```

Escape sequences inside strings:

```
print "Line one\nLine two"   # prints on two lines
print "Column\tone"          # tab between words
```

Useful string functions:

```
name = "  Jeremy  "
print trim(name)                         # "Jeremy"
print upper("hello")                     # "HELLO"
print replace("I love Python", "Python", "MyLang")
print split("one,two,three", ",")        # ['one', 'two', 'three']
print length("Hello")                    # 5
print contains("Hello World", "World")   # True
```

---

## If / Else

Make decisions with `if`. Close every block with `end`:

```
hp = 75

if hp > 50
    print "Healthy"
end
```

Add an `else` branch:

```
score = 45

if score >= 50
    print "Pass"
else
    print "Try again"
end
```

> For multiple conditions, nest `if` blocks inside `else`:

```
grade = 85

if grade >= 90
    print "A"
else
    if grade >= 80
        print "B"
    else
        print "C"
    end
end
```

---

## Loops

### For Loop — count a range

```
for i = 1 to 5
    print i
end
```

Prints `1 2 3 4 5` on separate lines.

### While Loop — repeat while true

```
count = 0

while count < 3
    print count
    count = count + 1
end
```

### Foreach Loop — iterate a list

```
names = ["Alice", "Bob", "Charlie"]

foreach name in names
    print name
end
```

---

## Functions

Define reusable blocks of code with `function`:

```
function greet name
    print "Hello, " + name + "!"
end

greet("Alice")
greet("Bob")
```

Return a value with `return`:

```
function add a b
    return a + b
end

result = add(10, 20)
print result   # 30
```

Add a doc comment on the line above the function — the IDE shows it as a hint:

```
# Calculate the area of a rectangle
function area width height
    return width * height
end
```

---

## Lists

Create a list with `[...]`:

```
scores = [42, 7, 99, 3, 55]
```

Access elements by 0-based index:

```
print scores[0]   # 42
print scores[4]   # 55
```

Update an element:

```
scores[2] = 100
```

Useful list functions:

```
scores = [42, 7, 99, 3, 55]

print length(scores)              # 5
print first(scores)               # 42
print last(scores)                # 55
print sort(scores)                # [3, 7, 42, 55, 99]
print reverse_list(scores)        # [55, 3, 99, 7, 42]
print contains_item(scores, 99)   # True
print index_of(scores, 7)         # 1

scores = append(scores, 88)
print scores                      # [42, 7, 99, 3, 55, 88]

scores = remove(scores, 3)
print scores                      # [42, 7, 99, 55, 88]
```

---

## Dictionaries

Store key-value data:

```
player = {
    "name": "Knight",
    "hp":   100,
    "mana": 50
}
```

Access and update values:

```
print player["hp"]   # 100

player["hp"] = 75
print player["hp"]   # 75
```

Useful dictionary functions:

```
print keys(player)               # ['name', 'hp', 'mana']
print values(player)             # ['Knight', 75, 50]
print exists(player, "hp")       # True
print exists(player, "gold")     # False
print get(player, "gold", 0)     # 0  (default)

player = delete(player, "mana")
```

---

## Reading Input

Ask the user for input with `input()`:

```
print "What is your name?"
name = input("> ")
print "Hello, " + name + "!"
```

With a prompt built in:

```
age_str = input("Enter your age: ")
age     = to_int(age_str)
print age + 1
```

---

## Type Conversion

Convert between types when needed:

```
num_str = "42"
num     = to_int(num_str)
print num + 1     # 43

n    = 100
text = to_str(n)
print length(text)   # 3

print to_bool(1)       # True
print to_bool("false") # False
print type_of(42)      # INTEGER
print type_of("hi")    # STRING
```

---

## File I/O

Read and write files — paths are relative to your script:

```
# Write a file
write_file("notes.txt", "My first note\n")

# Append to it
append_file("notes.txt", "Another line\n")

# Read it back
contents = read_file("notes.txt")
print contents

# Check if a file exists
print file_exists("notes.txt")   # True

# Clean up
delete_file("notes.txt")
```

Multi-line files — use `\n` for newlines:

```
write_file("log.txt", "Entry 1\nEntry 2\nEntry 3\n")
```

---

## Splitting Code Across Files

As your programs grow, split them into modules. Create `utils.my`:

```
# utils.my
function double n
    return n + n
end

function triple n
    return n + n + n
end
```

Then import it in `main.my`:

```
# main.my
import utils

print double(5)    # 10
print triple(5)    # 15
```

The `import` statement finds `.my` files in the same folder as your script.

---

## Comments

Start a line with `#` to write a comment:

```
# This is a comment — the interpreter ignores it
x = 10   # this part runs; only full-line # comments work
```

---

## Putting It All Together

Here's a small but complete program that uses many features:

```
# Score tracker

scores  = []
players = ["Alice", "Bob", "Charlie"]

function roll_dice
    return random(1, 20)
end

foreach player in players
    score = roll_dice()
    scores = append(scores, score)
    print player + " rolled " + to_str(score)
end

print ""
print "Results:"
print "Highest: " + to_str(last(sort(scores)))
print "Lowest:  " + to_str(first(sort(scores)))
print "Players: " + to_str(length(players))

write_file("results.txt", "Game complete\n")
print "Results saved."
```

---

## What's Next

- Read the **Language Specification** for the complete syntax reference
- Open the **MYTH IDE** (`python ide.py`) for autocomplete, syntax highlighting, and the integrated debugger
- Browse the `examples/` folder for working programs covering every feature
- Check the **Roadmap** for what's coming next


---

## Classes and Objects

*Added in v0.9.0*

Classes let you bundle data and behaviour together into reusable objects.

### Defining a Class

```
class Dog
    init name breed
        this.name  = name
        this.breed = breed
        this.tricks = []
    end

    method learn trick
        this.tricks = append(this.tricks, trick)
    end

    method show_tricks()
        print this.name + " knows:"
        foreach trick in this.tricks
            print "  - " + trick
        end
    end
end
```

- `class` / `end` wraps the whole definition
- `init` is the constructor — it runs automatically when you create an instance
- `method` defines something the object can do
- `this` always refers to the current object inside `init` and `method`

### Creating an Object

```
rex = Dog("Rex", "Labrador")
```

Call the class name like a function and pass the constructor arguments.

### Reading Properties

```
print rex.name    # Rex
print rex.breed   # Labrador
```

### Calling Methods

```
rex.learn("sit")
rex.learn("stay")
rex.learn("fetch")

rex.show_tricks()
```

### Methods That Return Values

```
class Calculator
    init value
        this.value = value
    end

    method doubled()
        return this.value * 2
    end
end

calc   = Calculator(21)
result = calc.doubled()
print result   # 42
```

### Multiple Instances

Each object is independent — changing one does not affect another:

```
a = Dog("Rex",   "Labrador")
b = Dog("Bella", "Poodle")

a.learn("sit")
b.learn("spin")

# Rex knows sit, Bella knows spin — completely separate
```

### Checking the Type

```
print type_of(rex)   # Dog
```

---

## Boolean Literals

Use `true` and `false` directly in conditions and assignments:

```
alive = true

if alive then
    print "Still running"
end

done = false
```

They work anywhere a value is expected — in variables, function arguments, return statements, and conditions.
