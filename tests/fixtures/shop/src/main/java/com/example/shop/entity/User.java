package com.example.shop.entity;

import jakarta.persistence.*;
import java.util.ArrayList;
import java.util.List;

/**
 * Usuario de la tienda. Este comentario menciona class Fake { y no debe confundir al parser.
 */
@Entity
@Table(name = "users", uniqueConstraints = @UniqueConstraint(columnNames = {"email"}))
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 120)
    private String name;

    // Un string con llaves: "}{" no debe romper nada
    private String greeting = "Hola {name}; bienvenido }";

    @OneToMany(mappedBy = "user", cascade = CascadeType.ALL)
    private List<Order> orders = new ArrayList<>();

    @Enumerated(EnumType.STRING)
    private Role role;

    protected User() {
    }

    public User(String name, Role role) {
        this.name = name;
        this.role = role;
    }

    public Long getId() {
        return id;
    }

    public List<Order> getOrders() {
        return orders;
    }
}
