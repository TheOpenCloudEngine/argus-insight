package com.example.domain;

import javax.persistence.Entity;
import javax.persistence.Table;
import javax.persistence.Id;
import javax.persistence.NamedQuery;
import javax.persistence.NamedQueries;
import javax.persistence.NamedNativeQuery;

@Entity
@Table(name = "orders")
@NamedQueries({
    @NamedQuery(
        name = "Order.findByStatus",
        query = "SELECT o FROM Order o WHERE o.status = :status"
    ),
    @NamedQuery(
        name = "Order.findByCustomer",
        query = "SELECT o FROM Order o JOIN o.customer c WHERE c.id = :customerId"
    )
})
@NamedNativeQuery(
    name = "Order.findRecentWithItems",
    query = "SELECT o.* FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.created_at > :since"
)
public class Order {

    @Id
    private Long id;

    private String status;
}
