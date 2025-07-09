package com.example.test;

import java.util.List;
import java.util.ArrayList;
import java.util.Map;

public class TestClass {
    private String name;
    private int value;
    
    public TestClass(String name, int value) {
        this.name = name;
        this.value = value;
    }
    
    public String getName() {
        return name;
    }
    
    public void setName(String name) {
        this.name = name;
    }
    
    private int getValue() {
        return value;
    }
    
    protected void setValue(int value) {
        this.value = value;
    }
}

interface TestInterface {
    void interfaceMethod();
    String getInterfaceName();
}

enum TestEnum {
    FIRST_VALUE,
    SECOND_VALUE,
    THIRD_VALUE
}

class InnerClass {
    public void innerMethod() {
        System.out.println("Inner method called");
    }
}