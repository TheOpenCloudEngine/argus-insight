package com.example.domain;

import javax.persistence.Entity;
import javax.persistence.Id;

@Entity
public class Category {

    @Id
    private Long id;

    private String name;
}
